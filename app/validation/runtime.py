from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Submission


RuntimeValidationOutcome = Literal["passed", "failed", "skipped"]


async def apply_runtime_validation_outcome(
    session: AsyncSession,
    submission_id: uuid.UUID,
    outcome: RuntimeValidationOutcome,
) -> bool:
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise ValueError("submission not found")
    submission.human_testing_required = outcome in {"failed", "skipped"}
    await session.flush()
    return submission.human_testing_required
