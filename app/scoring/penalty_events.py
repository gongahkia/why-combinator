from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PenaltyEvent, Submission
from app.leaderboard.cache import invalidate_leaderboard_scoreboard_cache


async def create_penalty_event_append_only(
    session: AsyncSession,
    submission_id: uuid.UUID,
    checkpoint_id: str,
    source: str,
    penalty_type: str,
    value: float,
    explanation: str,
) -> PenaltyEvent:
    row = PenaltyEvent(
        submission_id=submission_id,
        checkpoint_id=checkpoint_id,
        source=source,
        penalty_type=penalty_type,
        value=value,
        explanation=explanation,
    )
    session.add(row)
    await session.flush()
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise ValueError("penalty event submission not found")
    invalidate_leaderboard_scoreboard_cache(submission.run_id)
    return row
