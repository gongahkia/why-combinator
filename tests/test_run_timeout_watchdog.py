from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import RunState
from app.db.models import Challenge, Run
from app.scheduler.run_timeout import force_finalize_timed_out_runs


@pytest.mark.asyncio
async def test_timeout_watchdog_finalizes_at_exact_iteration_deadline(session: AsyncSession) -> None:
    start_time = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    challenge = Challenge(
        title="Run timeout watchdog test",
        prompt="Build and score a bounded-time MVP.",
        iteration_window_seconds=120,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(
        challenge_id=challenge.id,
        state=RunState.RUNNING,
        started_at=start_time,
        config_snapshot={},
    )
    session.add(run)
    await session.commit()

    pre_deadline_finalized = await force_finalize_timed_out_runs(session, now=start_time + timedelta(seconds=119))
    assert pre_deadline_finalized == []

    at_deadline_finalized = await force_finalize_timed_out_runs(session, now=start_time + timedelta(seconds=120))
    assert at_deadline_finalized == [str(run.id)]

    await session.refresh(run)
    assert run.state == RunState.COMPLETED
