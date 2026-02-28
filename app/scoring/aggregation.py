from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import JudgeScore

AggregationMode = Literal["average", "weighted_panel", "head_judge_override"]


@dataclass(frozen=True)
class AggregationResult:
    submission_id: uuid.UUID
    checkpoint_id: str
    mode: AggregationMode
    quality_score: float
    judge_count: int


def _average(scores: list[float]) -> float:
    return sum(scores) / len(scores) if scores else 0.0


def _weighted(scores: list[tuple[uuid.UUID, float]], weights: dict[uuid.UUID, float]) -> float:
    weighted_sum = 0.0
    total_weight = 0.0
    for judge_profile_id, score in scores:
        weight = weights.get(judge_profile_id, 1.0)
        weighted_sum += score * weight
        total_weight += weight
    return weighted_sum / total_weight if total_weight > 0 else 0.0


async def aggregate_submission_judge_scores(
    session: AsyncSession,
    submission_id: uuid.UUID,
    checkpoint_id: str,
    mode: AggregationMode = "average",
    judge_weights: dict[uuid.UUID, float] | None = None,
) -> AggregationResult:
    stmt: Select[tuple[JudgeScore]] = (
        select(JudgeScore)
        .options(selectinload(JudgeScore.judge_profile))
        .where(
            and_(
                JudgeScore.submission_id == submission_id,
                JudgeScore.checkpoint_id == checkpoint_id,
            )
        )
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return AggregationResult(
            submission_id=submission_id,
            checkpoint_id=checkpoint_id,
            mode=mode,
            quality_score=0.0,
            judge_count=0,
        )

    if mode == "average":
        quality_score = _average([row.score for row in rows])
    elif mode == "weighted_panel":
        quality_score = _weighted(
            scores=[(row.judge_profile_id, row.score) for row in rows],
            weights=judge_weights or {},
        )
    elif mode == "head_judge_override":
        head_judge_row = next((row for row in rows if row.judge_profile.head_judge), None)
        quality_score = head_judge_row.score if head_judge_row is not None else _average([row.score for row in rows])
    else:
        raise ValueError(f"unsupported aggregation mode: {mode}")

    return AggregationResult(
        submission_id=submission_id,
        checkpoint_id=checkpoint_id,
        mode=mode,
        quality_score=round(quality_score, 6),
        judge_count=len(rows),
    )
