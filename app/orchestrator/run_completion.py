from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Run, Submission
from app.leaderboard.materializer import materialize_leaderboard
from app.scoring.penalties import generate_non_production_penalties


async def complete_run(session: AsyncSession, run_id: uuid.UUID) -> dict[str, int]:
    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError("run not found")

    hacker_stmt: Select[tuple[Agent]] = select(Agent).where(
        Agent.run_id == run_id,
        Agent.role == AgentRole.HACKER,
    )
    hackers = (await session.execute(hacker_stmt)).scalars().all()
    auto_attempts_created = 0
    for hacker in hackers:
        attempt_stmt: Select[tuple[Submission]] = select(Submission).where(
            Submission.run_id == run_id,
            Submission.agent_id == hacker.id,
        )
        existing_attempt = (await session.execute(attempt_stmt)).scalars().first()
        if existing_attempt is not None:
            continue
        session.add(
            Submission(
                run_id=run_id,
                agent_id=hacker.id,
                state=SubmissionState.REJECTED,
                value_hypothesis="auto-generated attempt: no submission provided before run close",
                summary="auto-generated attempt object for non-producing hacker agent",
            )
        )
        auto_attempts_created += 1

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
        "auto_attempts_created": auto_attempts_created,
        "finalized_submissions": len(pending_submissions),
        "non_production_penalties": len(penalty_events),
        "leaderboard_entries": len(leaderboard_entries),
    }
