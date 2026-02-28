from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import RunState
from app.db.models import Run
from app.orchestrator.run_completion import complete_run
from app.validation.run_state_machine import apply_run_state_transition


def run_worker_heartbeat_key(run_id: uuid.UUID | str) -> str:
    return f"run:{run_id}:worker_heartbeat_at"


def load_run_heartbeat_stale_seconds() -> int:
    return int(os.getenv("RUN_HEARTBEAT_STALE_SECONDS", "180"))


def _ensure_utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def force_finalize_timed_out_runs(
    session: AsyncSession,
    now: datetime | None = None,
) -> list[str]:
    current_time = now or datetime.now(UTC)
    stmt: Select[tuple[Run]] = (
        select(Run)
        .options(selectinload(Run.challenge))
        .where(
            Run.state == RunState.RUNNING,
            Run.started_at.is_not(None),
        )
    )
    runs = (await session.execute(stmt)).scalars().all()
    finalized_run_ids: list[str] = []
    for run in runs:
        if run.started_at is None:
            continue
        deadline = run.started_at + timedelta(seconds=run.challenge.iteration_window_seconds)
        if current_time < deadline:
            continue
        await complete_run(session, run.id)
        finalized_run_ids.append(str(run.id))
    return finalized_run_ids


async def fail_stale_runs_without_worker_heartbeat(
    session: AsyncSession,
    redis_client: Redis,
    now: datetime | None = None,
) -> list[str]:
    current_time = _ensure_utc_timestamp(now or datetime.now(UTC))
    stale_after = timedelta(seconds=max(1, load_run_heartbeat_stale_seconds()))

    stmt: Select[tuple[Run]] = (
        select(Run)
        .options(selectinload(Run.challenge))
        .where(
            Run.state == RunState.RUNNING,
            Run.started_at.is_not(None),
        )
    )
    runs = (await session.execute(stmt)).scalars().all()
    failed_run_ids: list[str] = []
    for run in runs:
        if run.started_at is None:
            continue
        heartbeat_raw = await redis_client.get(run_worker_heartbeat_key(run.id))
        if heartbeat_raw is None:
            last_heartbeat = _ensure_utc_timestamp(run.started_at)
        else:
            try:
                last_heartbeat = _ensure_utc_timestamp(datetime.fromisoformat(heartbeat_raw))
            except ValueError:
                last_heartbeat = _ensure_utc_timestamp(run.started_at)
        if current_time - last_heartbeat <= stale_after:
            continue
        apply_run_state_transition(run, RunState.FAILED, now=current_time)
        failed_run_ids.append(str(run.id))

    if failed_run_ids:
        await session.commit()
    return failed_run_ids
