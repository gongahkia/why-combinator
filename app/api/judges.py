from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.models import Challenge, JudgeProfile

router = APIRouter(prefix="/challenges", tags=["judging"])


class JudgeProfileInput(BaseModel):
    domain: str = Field(min_length=2, max_length=255)
    scoring_style: str = Field(min_length=2, max_length=64)
    profile_prompt: str = Field(min_length=8)
    head_judge: bool = False


class JudgeProfileRegisterJSONRequest(BaseModel):
    profiles: list[JudgeProfileInput] = Field(min_length=1)


class JudgeProfileResponse(BaseModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    domain: str
    scoring_style: str
    profile_prompt: str
    head_judge: bool
    source_type: str
    created_at: datetime
    updated_at: datetime


@router.post(
    "/{challenge_id}/judge-profiles/json",
    status_code=status.HTTP_201_CREATED,
    response_model=list[JudgeProfileResponse],
)
async def register_judge_profiles_json(
    challenge_id: uuid.UUID,
    payload: JudgeProfileRegisterJSONRequest,
    session: AsyncSession = Depends(get_db_session),
) -> list[JudgeProfileResponse]:
    challenge = await session.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")

    profiles = [
        JudgeProfile(
            challenge_id=challenge_id,
            domain=item.domain,
            scoring_style=item.scoring_style,
            profile_prompt=item.profile_prompt,
            head_judge=item.head_judge,
            source_type="inline_json",
        )
        for item in payload.profiles
    ]
    session.add_all(profiles)
    await session.commit()
    for profile in profiles:
        await session.refresh(profile)

    return [
        JudgeProfileResponse(
            id=profile.id,
            challenge_id=profile.challenge_id,
            domain=profile.domain,
            scoring_style=profile.scoring_style,
            profile_prompt=profile.profile_prompt,
            head_judge=profile.head_judge,
            source_type=profile.source_type,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
        for profile in profiles
    ]
