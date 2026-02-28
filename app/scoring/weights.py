from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ScoringWeightConfig
from app.scoring.final_score import ActiveWeightsSnapshot


DEFAULT_WEIGHTS = ActiveWeightsSnapshot(
    quality=0.35,
    novelty=0.25,
    feasibility=0.2,
    criteria=0.2,
    similarity_penalty=0.2,
    too_safe_penalty=0.2,
    non_production_penalty=1.0,
)


async def resolve_active_weights_snapshot(
    session: AsyncSession,
    run_id: uuid.UUID,
    score_timestamp: datetime,
) -> ActiveWeightsSnapshot:
    stmt: Select[tuple[ScoringWeightConfig]] = (
        select(ScoringWeightConfig)
        .where(
            ScoringWeightConfig.run_id == run_id,
            ScoringWeightConfig.effective_from <= score_timestamp,
        )
        .order_by(desc(ScoringWeightConfig.effective_from))
        .limit(1)
    )
    config = (await session.execute(stmt)).scalar_one_or_none()
    if config is None:
        return DEFAULT_WEIGHTS

    weights = config.weights
    return ActiveWeightsSnapshot(
        quality=float(weights.get("quality", DEFAULT_WEIGHTS.quality)),
        novelty=float(weights.get("novelty", DEFAULT_WEIGHTS.novelty)),
        feasibility=float(weights.get("feasibility", DEFAULT_WEIGHTS.feasibility)),
        criteria=float(weights.get("criteria", DEFAULT_WEIGHTS.criteria)),
        similarity_penalty=float(weights.get("similarity_penalty", DEFAULT_WEIGHTS.similarity_penalty)),
        too_safe_penalty=float(weights.get("too_safe_penalty", DEFAULT_WEIGHTS.too_safe_penalty)),
        non_production_penalty=float(weights.get("non_production_penalty", DEFAULT_WEIGHTS.non_production_penalty)),
    )
