from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.enums import RunState
from app.db.models import Challenge, Run
from app.orchestrator.run_validation import RunStartValidationError, validate_domain_expert_judge_present

router = APIRouter(prefix="/challenges", tags=["runs"])


class RunResponse(BaseModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    state: RunState
    started_at: datetime | None
    ended_at: datetime | None
    config_snapshot: dict[str, object]
    created_at: datetime
    updated_at: datetime


@router.post(
    "/{challenge_id}/runs/start",
    status_code=status.HTTP_201_CREATED,
    response_model=RunResponse,
)
async def start_run(
    challenge_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    challenge = await session.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")

    try:
        await validate_domain_expert_judge_present(session, challenge_id)
    except RunStartValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    run = Run(
        challenge_id=challenge_id,
        state=RunState.RUNNING,
        started_at=datetime.now(timezone.utc),
        config_snapshot={},
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    return RunResponse.model_validate(run, from_attributes=True)
