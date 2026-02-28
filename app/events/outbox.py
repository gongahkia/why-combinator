from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import redis
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OutboxEvent
from app.events.bus import RunLifecycleEvent


def load_outbox_relay_batch_size() -> int:
    return int(os.getenv("OUTBOX_RELAY_BATCH_SIZE", "100"))


def load_outbox_dedup_ttl_seconds() -> int:
    return int(os.getenv("OUTBOX_DEDUP_TTL_SECONDS", str(7 * 24 * 60 * 60)))


@dataclass(frozen=True)
class OutboxRelayResult:
    processed: int
    published: int
    deduplicated: int
    failed: int


async def enqueue_outbox_event(
    session: AsyncSession,
    *,
    stream_name: str,
    event_type: str,
    event_key: str,
    payload: dict[str, object],
) -> OutboxEvent:
    existing_stmt: Select[tuple[OutboxEvent]] = select(OutboxEvent).where(OutboxEvent.event_key == event_key).limit(1)
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    event = OutboxEvent(
        stream_name=stream_name,
        event_type=event_type,
        event_key=event_key,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event


async def enqueue_run_lifecycle_event_outbox(
    session: AsyncSession,
    event: RunLifecycleEvent,
) -> OutboxEvent:
    event_key = f"run:{event.run_id}:{event.event_type}"
    return await enqueue_outbox_event(
        session,
        stream_name="run_events",
        event_type=event.event_type,
        event_key=event_key,
        payload=asdict(event),
    )


def _publish_outbox_once(
    redis_client: redis.Redis,
    *,
    event_id: str,
    stream_name: str,
    payload_json: str,
) -> bool:
    dedup_key = f"eventbus:published:{event_id}"
    script = """
    local dedup_key = KEYS[1]
    local ttl_ms = tonumber(ARGV[1])
    local stream_name = ARGV[2]
    local payload = ARGV[3]
    local inserted = redis.call('SETNX', dedup_key, '1')
    if inserted == 1 then
      redis.call('PEXPIRE', dedup_key, ttl_ms)
      redis.call('PUBLISH', stream_name, payload)
      return 1
    end
    return 0
    """
    result = int(
        redis_client.eval(
            script,
            1,
            dedup_key,
            max(1, load_outbox_dedup_ttl_seconds() * 1000),
            stream_name,
            payload_json,
        )
    )
    return result == 1


async def relay_outbox_events(
    session: AsyncSession,
    redis_client: redis.Redis,
    *,
    batch_size: int | None = None,
) -> OutboxRelayResult:
    effective_batch = max(1, batch_size or load_outbox_relay_batch_size())
    pending_stmt: Select[tuple[OutboxEvent]] = (
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.created_at.asc(), OutboxEvent.id.asc())
        .limit(effective_batch)
    )
    pending_events = (await session.execute(pending_stmt)).scalars().all()

    published = 0
    deduplicated = 0
    failed = 0
    for event in pending_events:
        payload_json = json.dumps(event.payload, sort_keys=True, separators=(",", ":"))
        try:
            emitted = _publish_outbox_once(
                redis_client,
                event_id=str(event.id),
                stream_name=event.stream_name,
                payload_json=payload_json,
            )
            event.publish_attempts += 1
            event.published_at = datetime.now(UTC)
            event.last_error = None
            if emitted:
                published += 1
            else:
                deduplicated += 1
        except Exception as exc:  # noqa: BLE001
            event.publish_attempts += 1
            event.last_error = str(exc)
            failed += 1

    await session.flush()
    return OutboxRelayResult(
        processed=len(pending_events),
        published=published,
        deduplicated=deduplicated,
        failed=failed,
    )
