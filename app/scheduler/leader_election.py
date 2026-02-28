from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis


SCHEDULER_LEADER_LOCK_KEY = "scheduler:leader:lock"
SCHEDULER_LEADER_HEARTBEAT_KEY = "scheduler:leader:heartbeat"


def load_scheduler_leader_lock_ttl_seconds() -> int:
    return int(os.getenv("SCHEDULER_LEADER_LOCK_TTL_SECONDS", "30"))


def load_scheduler_leader_id() -> str:
    configured = os.getenv("SCHEDULER_LEADER_ID", "").strip()
    if configured:
        return configured
    return f"{socket.gethostname()}:{os.getpid()}"


def _ensure_utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class SchedulerLeaderElectionResult:
    is_leader: bool
    leader_id: str
    lock_holder: str | None
    acquired_now: bool


async def try_acquire_or_renew_scheduler_leader(
    redis_client: Redis,
    leader_id: str,
) -> SchedulerLeaderElectionResult:
    ttl_seconds = max(1, load_scheduler_leader_lock_ttl_seconds())
    acquired = await redis_client.set(
        SCHEDULER_LEADER_LOCK_KEY,
        leader_id,
        ex=ttl_seconds,
        nx=True,
    )
    if acquired:
        return SchedulerLeaderElectionResult(
            is_leader=True,
            leader_id=leader_id,
            lock_holder=leader_id,
            acquired_now=True,
        )

    holder = await redis_client.get(SCHEDULER_LEADER_LOCK_KEY)
    if holder == leader_id:
        await redis_client.expire(SCHEDULER_LEADER_LOCK_KEY, ttl_seconds)
        return SchedulerLeaderElectionResult(
            is_leader=True,
            leader_id=leader_id,
            lock_holder=leader_id,
            acquired_now=False,
        )
    return SchedulerLeaderElectionResult(
        is_leader=False,
        leader_id=leader_id,
        lock_holder=holder,
        acquired_now=False,
    )


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
