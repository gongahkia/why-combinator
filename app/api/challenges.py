from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.api.rate_limit import rate_limit_dependency
from app.db.models import Challenge, Run

router = APIRouter(prefix="/challenges", tags=["challenges"])


class ChallengeCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    prompt: str = Field(min_length=10)
    iteration_window_seconds: int = Field(gt=0, le=86_400)
    minimum_quality_threshold: float = Field(ge=0.0, le=1.0)
    risk_appetite: Literal["conservative", "balanced", "aggressive"]
    complexity_slider: float = Field(ge=0.0, le=1.0)
    artifact_ttl_override_seconds: int | None = Field(default=None, gt=0, le=31_536_000)


class ChallengeResponse(BaseModel):
    id: uuid.UUID
    title: str
    prompt: str
    iteration_window_seconds: int
    minimum_quality_threshold: float
    risk_appetite: str
    complexity_slider: float
    artifact_ttl_override_seconds: int | None
    created_at: datetime
    updated_at: datetime


class ChallengeUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    prompt: str | None = Field(default=None, min_length=10)
    iteration_window_seconds: int | None = Field(default=None, gt=0, le=86_400)
    minimum_quality_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_appetite: Literal["conservative", "balanced", "aggressive"] | None = None
    complexity_slider: float | None = Field(default=None, ge=0.0, le=1.0)
    artifact_ttl_override_seconds: int | None = Field(default=None, gt=0, le=31_536_000)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ChallengeResponse)
async def create_challenge(
    payload: ChallengeCreateRequest,
    _rate_limit: None = rate_limit_dependency("challenge-mutation", capacity=30, refill_per_second=0.5),
    session: AsyncSession = Depends(get_db_session),
) -> ChallengeResponse:
    challenge = Challenge(
        title=payload.title,
        prompt=payload.prompt,
        iteration_window_seconds=payload.iteration_window_seconds,
        minimum_quality_threshold=payload.minimum_quality_threshold,
        risk_appetite=payload.risk_appetite,
        complexity_slider=payload.complexity_slider,
        artifact_ttl_override_seconds=payload.artifact_ttl_override_seconds,
    )
    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)

    return ChallengeResponse.model_validate(challenge, from_attributes=True)


@router.patch("/{challenge_id}", response_model=ChallengeResponse)
async def update_challenge(
    challenge_id: uuid.UUID,
    payload: ChallengeUpdateRequest,
    _rate_limit: None = rate_limit_dependency("challenge-mutation", capacity=30, refill_per_second=0.5),
    session: AsyncSession = Depends(get_db_session),
) -> ChallengeResponse:
    challenge = await session.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")

    started_runs_stmt: Select[tuple[int]] = select(func.count()).select_from(Run).where(
        Run.challenge_id == challenge_id,
        Run.started_at.is_not(None),
    )
    started_runs = (await session.execute(started_runs_stmt)).scalar_one()
    requested_changes = payload.model_dump(exclude_none=True)
    if started_runs > 0 and requested_changes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="challenge immutable fields cannot be edited after run start",
        )

    for field_name, value in requested_changes.items():
        setattr(challenge, field_name, value)
    await session.commit()
    await session.refresh(challenge)
    return ChallengeResponse.model_validate(challenge, from_attributes=True)
