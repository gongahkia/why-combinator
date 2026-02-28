from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JudgeScore


@dataclass(frozen=True)
class JudgeRubricOutput:
    judge_profile_id: uuid.UUID
    score: float
    rubric_weight: float = 1.0


def normalize_score(raw_score: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    if maximum <= minimum:
        raise ValueError("maximum must be greater than minimum")
    bounded = max(minimum, min(maximum, raw_score))
    return (bounded - minimum) / (maximum - minimum)


def score_quality_rubric(outputs: list[JudgeRubricOutput]) -> float:
    if not outputs:
        return 0.0
    numerator = sum(normalize_score(output.score) * output.rubric_weight for output in outputs)
    denominator = sum(output.rubric_weight for output in outputs) or 1.0
    return round(numerator / denominator, 6)


async def score_submission_quality(
    session: AsyncSession,
    submission_id: uuid.UUID,
    checkpoint_id: str,
) -> float:
    stmt: Select[tuple[JudgeScore]] = select(JudgeScore).where(
        and_(
            JudgeScore.submission_id == submission_id,
            JudgeScore.checkpoint_id == checkpoint_id,
        )
    )
    rows = (await session.execute(stmt)).scalars().all()
    return score_quality_rubric(
        outputs=[
            JudgeRubricOutput(judge_profile_id=row.judge_profile_id, score=row.score, rubric_weight=1.0)
            for row in rows
        ]
    )
