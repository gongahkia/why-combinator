from __future__ import annotations

import os
import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SubmissionState
from app.db.models import Agent, PenaltyEvent, Submission


def load_non_production_penalty_value() -> float:
    return float(os.getenv("NON_PRODUCTION_PENALTY_VALUE", "0.3"))


def load_non_production_penalty_multiplier() -> float:
    return float(os.getenv("NON_PRODUCTION_PENALTY_MULTIPLIER", "2.0"))


async def generate_non_production_penalties(
    session: AsyncSession,
    run_id: uuid.UUID,
    checkpoint_id: str = "run_end",
) -> list[PenaltyEvent]:
    penalty_value = load_non_production_penalty_value()
    heavy_multiplier = load_non_production_penalty_multiplier()
    agent_stmt: Select[tuple[uuid.UUID]] = select(Agent.id).where(Agent.run_id == run_id)
    agent_ids = (await session.execute(agent_stmt)).scalars().all()

    created_events: list[PenaltyEvent] = []
    for agent_id in agent_ids:
        accepted_stmt: Select[tuple[int]] = select(func.count()).select_from(Submission).where(
            Submission.run_id == run_id,
            Submission.agent_id == agent_id,
            Submission.state == SubmissionState.ACCEPTED,
        )
        accepted_count = (await session.execute(accepted_stmt)).scalar_one()
        if accepted_count > 0:
            continue

        submission_stmt: Select[tuple[Submission]] = select(Submission).where(
            Submission.run_id == run_id,
            Submission.agent_id == agent_id,
        )
        submissions = (await session.execute(submission_stmt)).scalars().all()
        for submission in submissions:
            exists_stmt: Select[tuple[int]] = select(func.count()).select_from(PenaltyEvent).where(
                PenaltyEvent.submission_id == submission.id,
                PenaltyEvent.checkpoint_id == checkpoint_id,
                PenaltyEvent.penalty_type == "non_production",
            )
            if (await session.execute(exists_stmt)).scalar_one() > 0:
                continue
            event = PenaltyEvent(
                submission_id=submission.id,
                checkpoint_id=checkpoint_id,
                source="run_completion_non_production",
                penalty_type="non_production",
                value=penalty_value * heavy_multiplier,
                explanation="agent produced zero accepted submissions by run end",
            )
            session.add(event)
            created_events.append(event)

    await session.flush()
    return created_events
