from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.models import Challenge, ChallengeApiKey

router = APIRouter(prefix="/challenges", tags=["auth"])


class RotateChallengeKeyResponse(BaseModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    api_key: str
    key_prefix: str
    key_last4: str
    created_at: datetime


@router.post("/{challenge_id}/api-keys/rotate", response_model=RotateChallengeKeyResponse)
async def rotate_challenge_api_key(
    challenge_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RotateChallengeKeyResponse:
    challenge = await session.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")

    await session.execute(
        update(ChallengeApiKey)
        .where(ChallengeApiKey.challenge_id == challenge_id, ChallengeApiKey.is_active.is_(True))
        .values(is_active=False)
    )

    raw_key = f"ck_{secrets.token_urlsafe(24)}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    key_prefix = raw_key[:8]
    key_last4 = raw_key[-4:]
    row = ChallengeApiKey(
        challenge_id=challenge_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        key_last4=key_last4,
        is_active=True,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return RotateChallengeKeyResponse(
        id=row.id,
        challenge_id=row.challenge_id,
        api_key=raw_key,
        key_prefix=row.key_prefix,
        key_last4=row.key_last4,
        created_at=row.created_at,
    )
