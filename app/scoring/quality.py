from __future__ import annotations

import os
import statistics
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


def _extract_judge_confidence(raw_response: dict[str, object]) -> float:
    parsed = raw_response.get("parsed")
    if isinstance(parsed, dict):
        confidence = parsed.get("confidence")
        if isinstance(confidence, (int, float)):
            return max(0.0, min(1.0, float(confidence)))
    confidence = raw_response.get("confidence")
    if isinstance(confidence, (int, float)):
        return max(0.0, min(1.0, float(confidence)))
    return 1.0


def normalize_score(raw_score: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    if maximum <= minimum:
        raise ValueError("maximum must be greater than minimum")
    bounded = max(minimum, min(maximum, raw_score))
    return (bounded - minimum) / (maximum - minimum)


def load_judge_outlier_dampener_threshold() -> float:
    return float(os.getenv("JUDGE_OUTLIER_DAMPENER_THRESHOLD", "0.25"))


def _outlier_dampener_factor(score: float, median_score: float, threshold: float) -> float:
    bounded_threshold = max(0.01, min(0.99, threshold))
    deviation = abs(score - median_score)
    if deviation <= bounded_threshold:
        return 1.0
    normalized_overage = (deviation - bounded_threshold) / max(1e-9, 1.0 - bounded_threshold)
    return max(0.1, 1.0 - normalized_overage)


def score_quality_rubric(outputs: list[JudgeRubricOutput]) -> float:
    if not outputs:
        return 0.0
    normalized_scores = [normalize_score(output.score) for output in outputs]
    median_score = statistics.median(normalized_scores)
    threshold = load_judge_outlier_dampener_threshold()
    dampened_weights = [
        output.rubric_weight * _outlier_dampener_factor(score, median_score, threshold)
        for output, score in zip(outputs, normalized_scores, strict=True)
    ]
    numerator = sum(score * weight for score, weight in zip(normalized_scores, dampened_weights, strict=True))
    denominator = sum(dampened_weights) or 1.0
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
            JudgeRubricOutput(
                judge_profile_id=row.judge_profile_id,
                score=row.score,
                rubric_weight=_extract_judge_confidence(row.raw_response if isinstance(row.raw_response, dict) else {}),
            )
            for row in rows
        ]
    )
