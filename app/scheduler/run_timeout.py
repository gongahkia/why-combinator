from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import RunState
from app.db.models import Run
from app.orchestrator.run_completion import complete_run


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
