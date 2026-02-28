from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.git_checkout import GitCheckoutError, isolated_git_checkout
from app.artifacts.retention import compute_artifact_expiry
from app.api.deps import get_db_session
from app.auth.quotas import QuotaUsageDelta, increment_quota_usage, quota_limits_from_request, resolve_quota_user_id
from app.db.idempotency import (
    get_idempotent_response,
    hash_request_payload,
    store_idempotent_response,
)
from app.db.models import Agent, Run, Submission
from app.db.enums import ArtifactType, SubmissionState
from app.db.models import Artifact, Challenge
from app.orchestrator.submission_summary import generate_submission_semantic_summary
from app.queue.jobs import enqueue_submission_score_job
from app.security.malware import MalwareScanError, scan_artifact_or_raise
from app.storage.adapter import build_object_storage_adapter
from app.storage.local import ArchiveExtractionError, validate_archive_members_safe
from app.validation.artifact_limits import ArtifactLimitError, validate_artifact_submission_limits
from app.validation.submission_state_machine import (
    SubmissionStateTransitionError,
    apply_submission_state_transition,
)

router = APIRouter(prefix="/runs", tags=["submissions"])


class SubmissionCreateRequest(BaseModel):
    agent_id: uuid.UUID
    value_hypothesis: str = Field(min_length=5)


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


class ArtifactIngestInput(BaseModel):
    artifact_type: ArtifactType
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=8)


class SubmissionIngestRequest(BaseModel):
    agent_id: uuid.UUID
    value_hypothesis: str = Field(min_length=5)
    artifacts: list[ArtifactIngestInput] = Field(min_length=1)


class SubmissionIngestResponse(BaseModel):
    submission: SubmissionResponse
    artifact_ids: list[uuid.UUID]


class RepositorySubmissionSourceRequest(BaseModel):
    agent_id: uuid.UUID
    value_hypothesis: str = Field(min_length=5)
    repository_url: str = Field(min_length=8)
    commit: str = Field(min_length=7, max_length=64)


class RepositorySubmissionSourceResponse(BaseModel):
    submission: SubmissionResponse
    artifact_id: uuid.UUID
    resolved_commit: str
    ingestion_job: dict[str, str]


class SubmissionStateTransitionRequest(BaseModel):
    state: SubmissionState


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
    challenge = await session.get(Challenge, run.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")
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

    summary = generate_submission_semantic_summary(
        challenge_prompt=challenge.prompt,
        value_hypothesis=payload.value_hypothesis,
    )
    submission = Submission(
        run_id=run_id,
        agent_id=payload.agent_id,
        value_hypothesis=payload.value_hypothesis,
        summary=summary,
    )
    session.add(submission)
    await session.flush()

    response_payload = SubmissionResponse.model_validate(submission, from_attributes=True).model_dump(mode="json")
    if idempotency_key:
        await store_idempotent_response(session, idempotency_scope, idempotency_key, request_hash, response_payload)
    await session.commit()
    await session.refresh(submission)
    return SubmissionResponse.model_validate(submission, from_attributes=True)


@router.post(
    "/{run_id}/submissions/ingest",
    status_code=status.HTTP_201_CREATED,
    response_model=SubmissionIngestResponse,
)
async def ingest_submission_transactional(
    run_id: uuid.UUID,
    request: Request,
    payload: SubmissionIngestRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SubmissionIngestResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    challenge = await session.get(Challenge, run.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")
    agent = await session.get(Agent, payload.agent_id)
    if agent is None or agent.run_id != run_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent does not belong to run")

    adapter = build_object_storage_adapter(request.app.state.settings.artifact_storage_path)
    decoded_artifacts = [(artifact_input, base64.b64decode(artifact_input.content_base64)) for artifact_input in payload.artifacts]
    try:
        validate_artifact_submission_limits(
            existing_count=0,
            existing_total_bytes=0,
            incoming_sizes=[len(content) for _, content in decoded_artifacts],
        )
    except ArtifactLimitError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    summary = generate_submission_semantic_summary(
        challenge_prompt=challenge.prompt,
        value_hypothesis=payload.value_hypothesis,
        artifact_descriptors=[f"{artifact.artifact_type.value}:{artifact.filename}" for artifact in payload.artifacts],
    )
    async with session.begin():
        submission = Submission(
            run_id=run_id,
            agent_id=payload.agent_id,
            value_hypothesis=payload.value_hypothesis,
            summary=summary,
        )
        session.add(submission)
        await session.flush()

        artifact_ids: list[uuid.UUID] = []
        ingested_total_bytes = 0
        for artifact_input, content in decoded_artifacts:
            try:
                validate_archive_members_safe(content, artifact_input.filename)
            except ArchiveExtractionError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"archive rejected by extraction guard: {exc}",
                ) from exc
            try:
                scan_artifact_or_raise(artifact_input.filename, content)
            except MalwareScanError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"artifact blocked by malware scanner ({exc.engine}): {exc.reason}",
                ) from exc
            storage_key = adapter.put_object(submission.id, artifact_input.filename, content)
            artifact = Artifact(
                submission_id=submission.id,
                artifact_type=artifact_input.artifact_type,
                storage_key=storage_key,
                content_hash=hashlib.sha256(content).hexdigest(),
                expires_at=compute_artifact_expiry(
                    challenge_override_seconds=challenge.artifact_ttl_override_seconds,
                ),
            )
            session.add(artifact)
            await session.flush()
            artifact_ids.append(artifact.id)
            ingested_total_bytes += len(content)

        await increment_quota_usage(
            session,
            quota_user_id=resolve_quota_user_id(request),
            delta=QuotaUsageDelta(artifact_storage_bytes=ingested_total_bytes),
            limits=quota_limits_from_request(request),
        )

    await session.refresh(submission)
    return SubmissionIngestResponse(
        submission=SubmissionResponse.model_validate(submission, from_attributes=True),
        artifact_ids=artifact_ids,
    )


@router.post(
    "/{run_id}/submissions/repository-source",
    status_code=status.HTTP_201_CREATED,
    response_model=RepositorySubmissionSourceResponse,
)
async def attach_repository_submission_source(
    run_id: uuid.UUID,
    payload: RepositorySubmissionSourceRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> RepositorySubmissionSourceResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    challenge = await session.get(Challenge, run.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")
    agent = await session.get(Agent, payload.agent_id)
    if agent is None or agent.run_id != run_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="agent does not belong to run")

    checkout_root = os.path.join(request.app.state.settings.artifact_storage_path, "repo-checkouts")
    try:
        checkout = isolated_git_checkout(
            repository_url=payload.repository_url,
            commit=payload.commit,
            destination_root=checkout_root,
            shallow_depth=1,
        )
    except GitCheckoutError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"repository checkout failed: {exc}") from exc

    summary = generate_submission_semantic_summary(
        challenge_prompt=challenge.prompt,
        value_hypothesis=payload.value_hypothesis,
        artifact_descriptors=[f"repository:{payload.repository_url}@{checkout.commit}"],
    )

    submission = Submission(
        run_id=run_id,
        agent_id=payload.agent_id,
        value_hypothesis=payload.value_hypothesis,
        summary=summary,
    )
    session.add(submission)
    await session.flush()

    root_path = Path(request.app.state.settings.artifact_storage_path)
    checkout_path = Path(checkout.checkout_path)
    try:
        storage_key = str(checkout_path.relative_to(root_path))
    except ValueError:
        storage_key = str(checkout_path)
    repo_storage_bytes = 0
    if checkout_path.exists():
        for path in checkout_path.rglob("*"):
            if path.is_file():
                repo_storage_bytes += path.stat().st_size

    artifact = Artifact(
        submission_id=submission.id,
        artifact_type=ArtifactType.CLI_PACKAGE,
        storage_key=storage_key,
        content_hash=hashlib.sha256(f"{payload.repository_url}@{checkout.commit}".encode("utf-8")).hexdigest(),
        expires_at=compute_artifact_expiry(
            challenge_override_seconds=challenge.artifact_ttl_override_seconds,
        ),
    )
    session.add(artifact)
    await session.flush()
    await increment_quota_usage(
        session,
        quota_user_id=resolve_quota_user_id(request),
        delta=QuotaUsageDelta(artifact_storage_bytes=repo_storage_bytes),
        limits=quota_limits_from_request(request),
    )
    await session.commit()
    await session.refresh(submission)
    ingestion_job = enqueue_submission_score_job(submission.id, "repository_ingest")
    return RepositorySubmissionSourceResponse(
        submission=SubmissionResponse.model_validate(submission, from_attributes=True),
        artifact_id=artifact.id,
        resolved_commit=checkout.commit,
        ingestion_job=ingestion_job,
    )


@router.post(
    "/{run_id}/submissions/{submission_id}/state",
    response_model=SubmissionResponse,
)
async def transition_submission_state(
    run_id: uuid.UUID,
    submission_id: uuid.UUID,
    payload: SubmissionStateTransitionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SubmissionResponse:
    submission = await session.get(Submission, submission_id)
    if submission is None or submission.run_id != run_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found")

    try:
        apply_submission_state_transition(submission, payload.state)
    except SubmissionStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    await session.commit()
    await session.refresh(submission)
    return SubmissionResponse.model_validate(submission, from_attributes=True)
