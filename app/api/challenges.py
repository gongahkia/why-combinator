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
from app.auth.quotas import QuotaUsageDelta, current_quota_user_id, increment_quota_usage, quota_limits_from_settings
from app.config import load_settings
from app.db.models import Challenge, JudgeProfile, Run
from app.judging.versioning import create_judge_profile_version_snapshot

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


class ChallengeCloneRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)


class ChallengeCloneResponse(ChallengeResponse):
    source_challenge_id: uuid.UUID
    cloned_judge_profile_count: int
    is_draft: bool


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
    await session.flush()
    await increment_quota_usage(
        session,
        quota_user_id=current_quota_user_id(),
        delta=QuotaUsageDelta(challenges_created=1),
        limits=quota_limits_from_settings(load_settings()),
    )
    await session.commit()
    await session.refresh(challenge)

    return ChallengeResponse.model_validate(challenge, from_attributes=True)


@router.post(
    "/{challenge_id}/clone",
    status_code=status.HTTP_201_CREATED,
    response_model=ChallengeCloneResponse,
)
async def clone_challenge(
    challenge_id: uuid.UUID,
    payload: ChallengeCloneRequest | None = None,
    _rate_limit: None = rate_limit_dependency("challenge-mutation", capacity=30, refill_per_second=0.5),
    session: AsyncSession = Depends(get_db_session),
) -> ChallengeCloneResponse:
    source_challenge = await session.get(Challenge, challenge_id)
    if source_challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")

    requested_title = payload.title if payload is not None else None
    cloned_title = requested_title if requested_title is not None else f"{source_challenge.title} (Draft)"
    cloned_challenge = Challenge(
        title=cloned_title,
        prompt=source_challenge.prompt,
        iteration_window_seconds=source_challenge.iteration_window_seconds,
        minimum_quality_threshold=source_challenge.minimum_quality_threshold,
        risk_appetite=source_challenge.risk_appetite,
        complexity_slider=source_challenge.complexity_slider,
        artifact_ttl_override_seconds=source_challenge.artifact_ttl_override_seconds,
    )
    session.add(cloned_challenge)
    await session.flush()

    source_judge_profiles_stmt: Select[tuple[JudgeProfile]] = select(JudgeProfile).where(
        JudgeProfile.challenge_id == challenge_id
    )
    source_judge_profiles = (await session.execute(source_judge_profiles_stmt)).scalars().all()
    cloned_judge_profiles = [
        JudgeProfile(
            challenge_id=cloned_challenge.id,
            domain=profile.domain,
            scoring_style=profile.scoring_style,
            profile_prompt=profile.profile_prompt,
            head_judge=profile.head_judge,
            source_type=profile.source_type,
        )
        for profile in source_judge_profiles
    ]
    if cloned_judge_profiles:
        session.add_all(cloned_judge_profiles)
        await session.flush()
        await create_judge_profile_version_snapshot(session, cloned_challenge.id, activate=True)

    await increment_quota_usage(
        session,
        quota_user_id=current_quota_user_id(),
        delta=QuotaUsageDelta(challenges_created=1),
        limits=quota_limits_from_settings(load_settings()),
    )
    await session.commit()
    await session.refresh(cloned_challenge)

    cloned_response = ChallengeResponse.model_validate(cloned_challenge, from_attributes=True)
    return ChallengeCloneResponse(
        **cloned_response.model_dump(),
        source_challenge_id=challenge_id,
        cloned_judge_profile_count=len(cloned_judge_profiles),
        is_draft=True,
    )


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
