from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import RunState
from app.db.models import Run
from app.queue.jobs import checkpoint_score


def load_checkpoint_interval_seconds() -> int:
    return int(os.getenv("CHECKPOINT_INTERVAL_SECONDS", "60"))


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

        checkpoint_score.delay(str(run.id))
        await redis_client.set(key, (current_time + interval).isoformat())
        scheduled_run_ids.append(str(run.id))

    return scheduled_run_ids
