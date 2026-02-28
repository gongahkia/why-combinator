from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import RunState, SubmissionState
from app.db.models import Run, Submission
from app.leaderboard.materializer import materialize_leaderboard
from app.scoring.penalties import generate_non_production_penalties


async def complete_run(session: AsyncSession, run_id: uuid.UUID) -> dict[str, int]:
    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError("run not found")

    pending_stmt: Select[tuple[Submission]] = select(Submission).where(
        Submission.run_id == run_id,
        Submission.state == SubmissionState.PENDING,
    )
    pending_submissions = (await session.execute(pending_stmt)).scalars().all()
    for submission in pending_submissions:
        submission.state = SubmissionState.REJECTED

    penalty_events = await generate_non_production_penalties(session, run_id, checkpoint_id="run_end")
    leaderboard_entries = await materialize_leaderboard(session, run_id)

    run.state = RunState.COMPLETED
    run.ended_at = datetime.now(UTC)
    await session.commit()
    return {
        "finalized_submissions": len(pending_submissions),
        "non_production_penalties": len(penalty_events),
        "leaderboard_entries": len(leaderboard_entries),
    }
