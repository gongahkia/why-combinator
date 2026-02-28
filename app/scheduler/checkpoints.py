from __future__ import annotations

import hashlib
import os
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import RunState
from app.db.models import CheckpointSnapshot, Run
from app.observability.trace import new_trace_id
from app.queue.jobs import checkpoint_score
from app.scheduler.leader_election import (
    load_scheduler_leader_id,
    publish_scheduler_leader_heartbeat,
    try_acquire_or_renew_scheduler_leader,
)


def load_checkpoint_interval_seconds() -> int:
    return int(os.getenv("CHECKPOINT_INTERVAL_SECONDS", "60"))


def load_checkpoint_max_enqueues_per_tick() -> int:
    return int(os.getenv("CHECKPOINT_MAX_ENQUEUES_PER_TICK", "100"))


def load_checkpoint_jitter_seconds() -> int:
    return int(os.getenv("CHECKPOINT_JITTER_SECONDS", "0"))


def _weighted_fair_due_order(runs: list[Run]) -> list[Run]:
    per_challenge: dict[str, deque[Run]] = defaultdict(deque)
    for run in runs:
        per_challenge[str(run.challenge_id)].append(run)

    ordered: list[Run] = []
    challenge_ids = sorted(per_challenge.keys())
    while challenge_ids:
        next_ids: list[str] = []
        for challenge_id in challenge_ids:
            queue = per_challenge[challenge_id]
            if not queue:
                continue
            ordered.append(queue.popleft())
            if queue:
                next_ids.append(challenge_id)
        challenge_ids = next_ids
    return ordered


def _ensure_utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _run_checkpoint_jitter_seconds(
    run_id: uuid.UUID,
    *,
    interval_seconds: int,
    jitter_window_seconds: int,
) -> int:
    capped_window = max(0, min(jitter_window_seconds, max(0, interval_seconds - 1)))
    if capped_window <= 0:
        return 0
    digest = hashlib.sha256(str(run_id).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], byteorder="big") % (capped_window + 1)


def _apply_checkpoint_jitter(
    base_checkpoint_at: datetime,
    *,
    run_id: uuid.UUID,
    interval_seconds: int,
) -> datetime:
    jitter_seconds = _run_checkpoint_jitter_seconds(
        run_id,
        interval_seconds=interval_seconds,
        jitter_window_seconds=load_checkpoint_jitter_seconds(),
    )
    return base_checkpoint_at + timedelta(seconds=jitter_seconds)


async def _resolve_resume_checkpoint_at(
    session: AsyncSession,
    run: Run,
    interval: timedelta,
) -> datetime | None:
    if run.started_at is None:
        return None
    snapshot_stmt: Select[tuple[datetime]] = (
        select(CheckpointSnapshot.captured_at)
        .where(CheckpointSnapshot.run_id == run.id)
        .order_by(CheckpointSnapshot.captured_at.desc())
        .limit(1)
    )
    latest_checkpoint_at = (await session.execute(snapshot_stmt)).scalar_one_or_none()
    if latest_checkpoint_at is None:
        return _ensure_utc_timestamp(run.started_at)
    return _ensure_utc_timestamp(latest_checkpoint_at) + interval


async def enqueue_periodic_checkpoint_scores(
    session: AsyncSession,
    redis_client: Redis,
    now: datetime | None = None,
) -> list[str]:
    current_time = now or datetime.now(UTC)
    interval_seconds = max(1, load_checkpoint_interval_seconds())
    interval = timedelta(seconds=interval_seconds)
    scheduled_run_ids: list[str] = []
    leader_id = load_scheduler_leader_id()
    election = await try_acquire_or_renew_scheduler_leader(redis_client, leader_id)
    if not election.is_leader:
        return []
    await publish_scheduler_leader_heartbeat(redis_client, leader_id, now=current_time)

    running_stmt: Select[tuple[Run]] = (
        select(Run)
        .options(selectinload(Run.challenge))
        .where(
            Run.state == RunState.RUNNING,
            Run.started_at.is_not(None),
        )
    )
    runs = (await session.execute(running_stmt)).scalars().all()
    due_runs: list[Run] = []
    for run in runs:
        if run.started_at is None:
            continue
        deadline = run.started_at + timedelta(seconds=run.challenge.iteration_window_seconds)
        if current_time >= deadline:
            continue

        key = f"run:{run.id}:next_checkpoint_at"
        next_checkpoint_raw = await redis_client.get(key)
        if next_checkpoint_raw is None:
            base_checkpoint_at = await _resolve_resume_checkpoint_at(session, run, interval)
            if base_checkpoint_at is None:
                continue
            next_checkpoint = _apply_checkpoint_jitter(
                base_checkpoint_at,
                run_id=run.id,
                interval_seconds=interval_seconds,
            )
            await redis_client.set(key, next_checkpoint.isoformat())
        else:
            next_checkpoint = _ensure_utc_timestamp(datetime.fromisoformat(next_checkpoint_raw))

        if current_time < next_checkpoint:
            continue

        due_runs.append(run)

    max_enqueues = max(1, load_checkpoint_max_enqueues_per_tick())
    for run in _weighted_fair_due_order(due_runs)[:max_enqueues]:
        checkpoint_score.delay(str(run.id), new_trace_id())
        key = f"run:{run.id}:next_checkpoint_at"
        next_checkpoint = _apply_checkpoint_jitter(
            current_time + interval,
            run_id=run.id,
            interval_seconds=interval_seconds,
        )
        await redis_client.set(key, next_checkpoint.isoformat())
        scheduled_run_ids.append(str(run.id))

    return scheduled_run_ids
