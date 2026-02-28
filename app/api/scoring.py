from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.models import Run, ScoringWeightConfig

router = APIRouter(prefix="/runs", tags=["scoring"])


class ScoringWeightsPayload(BaseModel):
    quality: float = Field(ge=0.0)
    novelty: float = Field(ge=0.0)
    feasibility: float = Field(ge=0.0)
    criteria: float = Field(ge=0.0)
    similarity_penalty: float = Field(ge=0.0, le=1.0)
    too_safe_penalty: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_criteria_weights(self) -> ScoringWeightsPayload:
        total = self.quality + self.novelty + self.feasibility + self.criteria
        if abs(total - 1.0) > 1e-6:
            raise ValueError("quality + novelty + feasibility + criteria must sum to 1.0")
        return self


class ScoringWeightsUpdateRequest(BaseModel):
    expected_config_version: int = Field(ge=0)
    effective_from: datetime
    weights: ScoringWeightsPayload


class ScoringWeightsUpdateResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    effective_from: datetime
    weights: ScoringWeightsPayload
    config_version: int
    created_at: datetime
    updated_at: datetime


@router.post("/{run_id}/scoring-weights", status_code=status.HTTP_201_CREATED, response_model=ScoringWeightsUpdateResponse)
async def update_scoring_weights(
    run_id: uuid.UUID,
    payload: ScoringWeightsUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ScoringWeightsUpdateResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    if payload.expected_config_version != run.config_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "config version mismatch: expected "
                f"{payload.expected_config_version}, current {run.config_version}"
            ),
        )

    stmt: Select[tuple[ScoringWeightConfig]] = (
        select(ScoringWeightConfig)
        .where(ScoringWeightConfig.run_id == run_id)
        .order_by(desc(ScoringWeightConfig.effective_from))
        .limit(1)
    )
    latest = (await session.execute(stmt)).scalar_one_or_none()
    if latest and payload.effective_from <= latest.effective_from:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="effective_from must be greater than the latest configured effective_from",
        )

    config = ScoringWeightConfig(
        run_id=run_id,
        effective_from=payload.effective_from,
        weights=payload.weights.model_dump(),
    )
    session.add(config)
    run.config_version += 1
    await session.commit()
    await session.refresh(config)
    await session.refresh(run)

    return ScoringWeightsUpdateResponse(
        id=config.id,
        run_id=config.run_id,
        effective_from=config.effective_from,
        weights=ScoringWeightsPayload(**config.weights),
        config_version=run.config_version,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )
