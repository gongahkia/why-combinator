from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.models import Challenge

router = APIRouter(prefix="/challenges", tags=["challenges"])


class ChallengeCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    prompt: str = Field(min_length=10)
    iteration_window_seconds: int = Field(gt=0, le=86_400)
    minimum_quality_threshold: float = Field(ge=0.0, le=1.0)
    risk_appetite: Literal["conservative", "balanced", "aggressive"]
    complexity_slider: float = Field(ge=0.0, le=1.0)


class ChallengeResponse(BaseModel):
    id: uuid.UUID
    title: str
    prompt: str
    iteration_window_seconds: int
    minimum_quality_threshold: float
    risk_appetite: str
    complexity_slider: float
    created_at: datetime
    updated_at: datetime


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ChallengeResponse)
async def create_challenge(payload: ChallengeCreateRequest, session: AsyncSession = Depends(get_db_session)) -> ChallengeResponse:
    challenge = Challenge(
        title=payload.title,
        prompt=payload.prompt,
        iteration_window_seconds=payload.iteration_window_seconds,
        minimum_quality_threshold=payload.minimum_quality_threshold,
        risk_appetite=payload.risk_appetite,
        complexity_slider=payload.complexity_slider,
    )
    session.add(challenge)
    await session.commit()
    await session.refresh(challenge)

    return ChallengeResponse.model_validate(challenge, from_attributes=True)
