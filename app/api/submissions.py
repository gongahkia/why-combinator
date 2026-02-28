from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.idempotency import (
    get_idempotent_response,
    hash_request_payload,
    store_idempotent_response,
)
from app.db.models import Agent, Run, Submission

router = APIRouter(prefix="/runs", tags=["submissions"])


class SubmissionCreateRequest(BaseModel):
    agent_id: uuid.UUID
    value_hypothesis: str = Field(min_length=5)
    summary: str = Field(min_length=10)


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    agent_id: uuid.UUID
    state: str
    value_hypothesis: str
    summary: str
    accepted_at: datetime | None
    human_testing_required: bool
    created_at: datetime
    updated_at: datetime


@router.post("/{run_id}/submissions", status_code=status.HTTP_201_CREATED, response_model=SubmissionResponse)
async def create_submission(
    run_id: uuid.UUID,
    payload: SubmissionCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_db_session),
) -> SubmissionResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    agent = await session.get(Agent, payload.agent_id)
    if agent is None or agent.run_id != run_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent does not belong to run")

    request_payload = payload.model_dump(mode="json")
    request_hash = hash_request_payload(request_payload)
    idempotency_scope = f"submission_create:{run_id}"
    if idempotency_key:
        existing = await get_idempotent_response(session, idempotency_scope, idempotency_key, request_hash)
        if existing is not None:
            return SubmissionResponse.model_validate(existing)

    submission = Submission(
        run_id=run_id,
        agent_id=payload.agent_id,
        value_hypothesis=payload.value_hypothesis,
        summary=payload.summary,
    )
    session.add(submission)
    await session.flush()

    response_payload = SubmissionResponse.model_validate(submission, from_attributes=True).model_dump(mode="json")
    if idempotency_key:
        await store_idempotent_response(session, idempotency_scope, idempotency_key, request_hash, response_payload)
    await session.commit()
    await session.refresh(submission)
    return SubmissionResponse.model_validate(submission, from_attributes=True)
