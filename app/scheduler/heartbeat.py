from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.scheduler.checkpoints import enqueue_periodic_checkpoint_scores


SCHEDULER_LEADER_HEARTBEAT_KEY = "scheduler:leader:heartbeat"
SCHEDULER_LEADER_FAILOVER_REQUEST_KEY = "scheduler:leader:failover_requested"


def load_scheduler_heartbeat_stale_seconds() -> int:
    return int(os.getenv("SCHEDULER_HEARTBEAT_STALE_SECONDS", "45"))


def load_scheduler_failover_request_ttl_seconds() -> int:
    return int(os.getenv("SCHEDULER_FAILOVER_REQUEST_TTL_SECONDS", "120"))


def _ensure_utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class SchedulerHeartbeatMonitorResult:
    failover_triggered: bool
    reason: str
    scheduled_run_ids: list[str]


async def publish_scheduler_leader_heartbeat(
    redis_client: Redis,
    leader_id: str,
    now: datetime | None = None,
) -> None:
    current_time = _ensure_utc_timestamp(now or datetime.now(UTC))
    payload = {
        "leader_id": leader_id,
        "heartbeat_at": current_time.isoformat(),
    }
    await redis_client.set(SCHEDULER_LEADER_HEARTBEAT_KEY, json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _parse_heartbeat_timestamp(raw_payload: str) -> datetime | None:
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    heartbeat_raw = payload.get("heartbeat_at")
    if not isinstance(heartbeat_raw, str):
        return None
    try:
        heartbeat_at = datetime.fromisoformat(heartbeat_raw)
    except ValueError:
        return None
    return _ensure_utc_timestamp(heartbeat_at)


async def monitor_scheduler_heartbeat_and_trigger_failover(
    session: AsyncSession,
    redis_client: Redis,
    now: datetime | None = None,
) -> SchedulerHeartbeatMonitorResult:
    current_time = _ensure_utc_timestamp(now or datetime.now(UTC))
    raw_heartbeat = await redis_client.get(SCHEDULER_LEADER_HEARTBEAT_KEY)
    reason = "healthy"
    should_failover = False

    if raw_heartbeat is None:
        should_failover = True
        reason = "missing_heartbeat"
    else:
        heartbeat_at = _parse_heartbeat_timestamp(raw_heartbeat)
        if heartbeat_at is None:
            should_failover = True
            reason = "invalid_heartbeat_payload"
        else:
            age_seconds = max(0.0, (current_time - heartbeat_at).total_seconds())
            if age_seconds > load_scheduler_heartbeat_stale_seconds():
                should_failover = True
                reason = f"stale_heartbeat:{round(age_seconds, 3)}s"

    if not should_failover:
        return SchedulerHeartbeatMonitorResult(
            failover_triggered=False,
            reason=reason,
            scheduled_run_ids=[],
        )

    failover_payload = {
        "reason": reason,
        "triggered_at": current_time.isoformat(),
    }
    await redis_client.set(
        SCHEDULER_LEADER_FAILOVER_REQUEST_KEY,
        json.dumps(failover_payload, sort_keys=True, separators=(",", ":")),
        ex=max(1, load_scheduler_failover_request_ttl_seconds()),
    )
    scheduled_run_ids = await enqueue_periodic_checkpoint_scores(session, redis_client, now=current_time)
    return SchedulerHeartbeatMonitorResult(
        failover_triggered=True,
        reason=reason,
        scheduled_run_ids=scheduled_run_ids,
    )
