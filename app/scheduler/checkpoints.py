from __future__ import annotations

import os
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import RunState
from app.db.models import Run
from app.observability.trace import new_trace_id
from app.queue.jobs import checkpoint_score


def load_checkpoint_interval_seconds() -> int:
    return int(os.getenv("CHECKPOINT_INTERVAL_SECONDS", "60"))


def load_checkpoint_max_enqueues_per_tick() -> int:
    return int(os.getenv("CHECKPOINT_MAX_ENQUEUES_PER_TICK", "100"))


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


async def enqueue_periodic_checkpoint_scores(
    session: AsyncSession,
    redis_client: Redis,
    now: datetime | None = None,
) -> list[str]:
    current_time = now or datetime.now(UTC)
    interval = timedelta(seconds=load_checkpoint_interval_seconds())
    scheduled_run_ids: list[str] = []

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
            next_checkpoint = run.started_at
        else:
            next_checkpoint = datetime.fromisoformat(next_checkpoint_raw)

        if current_time < next_checkpoint:
            continue

        due_runs.append(run)

    max_enqueues = max(1, load_checkpoint_max_enqueues_per_tick())
    for run in _weighted_fair_due_order(due_runs)[:max_enqueues]:
        checkpoint_score.delay(str(run.id), new_trace_id())
        key = f"run:{run.id}:next_checkpoint_at"
        await redis_client.set(key, (current_time + interval).isoformat())
        scheduled_run_ids.append(str(run.id))

    return scheduled_run_ids
