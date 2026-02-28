from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import SubmissionState
from app.db.models import Submission


async def apply_quality_threshold_gate(
    session: AsyncSession,
    submission_id: uuid.UUID,
    quality_score: float,
) -> bool:
    stmt: Select[tuple[Submission]] = (
        select(Submission)
        .options(selectinload(Submission.run).selectinload(Submission.run.challenge))
        .where(Submission.id == submission_id)
    )
    submission = (await session.execute(stmt)).scalar_one_or_none()
    if submission is None:
        raise ValueError("submission not found")

    threshold = submission.run.challenge.minimum_quality_threshold
    is_accepted = quality_score >= threshold
    if is_accepted:
        submission.state = SubmissionState.ACCEPTED
        submission.accepted_at = datetime.now(UTC)
    else:
        submission.state = SubmissionState.REJECTED
        submission.accepted_at = None
    await session.flush()
    return is_accepted
