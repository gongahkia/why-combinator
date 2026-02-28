from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import SubmissionState
from app.db.models import Run, Submission
from app.validation.submission_state_machine import apply_submission_state_transition


async def apply_quality_threshold_gate(
    session: AsyncSession,
    submission_id: uuid.UUID,
    quality_score: float,
) -> bool:
    stmt: Select[tuple[Submission]] = (
        select(Submission)
        .options(selectinload(Submission.run).selectinload(Run.challenge))
        .where(Submission.id == submission_id)
    )
    submission = (await session.execute(stmt)).scalar_one_or_none()
    if submission is None:
        raise ValueError("submission not found")

    threshold = submission.run.challenge.minimum_quality_threshold
    is_accepted = quality_score >= threshold
    apply_submission_state_transition(submission, target_state=SubmissionState.SCORED, now=datetime.now(UTC))
    target_state = SubmissionState.ACCEPTED if is_accepted else SubmissionState.REJECTED
    apply_submission_state_transition(submission, target_state=target_state, now=datetime.now(UTC))
    await session.flush()
    return is_accepted
