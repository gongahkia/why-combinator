from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.enums import ArtifactType
from app.db.models import Artifact, Challenge, Run, Submission
from app.artifacts.retention import ArtifactRetentionPolicyError, compute_artifact_expiry
from app.artifacts.retention import is_artifact_expired
from app.auth.quotas import QuotaUsageDelta, increment_quota_usage, resolve_quota_user_id
from app.security.malware import MalwareScanError, scan_artifact_or_raise
from app.storage.adapter import ObjectStorageAdapter, build_object_storage_adapter
from app.storage.local import ArchiveExtractionError, validate_archive_members_safe
from app.storage.presign import ArtifactPresignError, create_artifact_download_token, validate_artifact_download_token
from app.validation.artifact_limits import ArtifactLimitError, validate_artifact_submission_limits
from app.validation.readme import validate_minimum_readme_content
from app.validation.value_hypothesis import validate_measurable_value_hypothesis

router = APIRouter(prefix="/submissions", tags=["artifacts"])

ARTIFACT_TYPE_ALIASES: dict[str, ArtifactType] = {
    "web_app_bundle": ArtifactType.WEB_BUNDLE,
    "web_bundle": ArtifactType.WEB_BUNDLE,
    "cli_package": ArtifactType.CLI_PACKAGE,
    "api_service_bundle": ArtifactType.API_SERVICE,
    "api_service": ArtifactType.API_SERVICE,
    "notebook_file": ArtifactType.NOTEBOOK,
    "notebook": ArtifactType.NOTEBOOK,
}


class ArtifactUploadResponse(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    artifact_type: ArtifactType
    storage_key: str
    content_hash: str
    created_at: datetime
    updated_at: datetime


class SubmissionValidationResponse(BaseModel):
    submission_id: uuid.UUID
    valid: bool
    errors: list[str]


class ArtifactDownloadURLRequest(BaseModel):
    ttl_seconds: int | None = None


class ArtifactDownloadURLResponse(BaseModel):
    artifact_id: uuid.UUID
    submission_id: uuid.UUID
    download_url: str
    expires_at: datetime


@router.post(
    "/{submission_id}/artifacts",
    status_code=status.HTTP_201_CREATED,
    response_model=ArtifactUploadResponse,
)
async def upload_artifact(
    submission_id: uuid.UUID,
    request: Request,
    artifact_type: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> ArtifactUploadResponse:
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found")
    run = await session.get(Run, submission.run_id)
    challenge = await session.get(Challenge, run.challenge_id) if run is not None else None

    normalized_type = ARTIFACT_TYPE_ALIASES.get(artifact_type.strip().lower())
    if normalized_type is None:
        allowed = ", ".join(sorted(ARTIFACT_TYPE_ALIASES))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unsupported artifact_type; expected one of: {allowed}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="artifact file is empty")
    adapter = build_object_storage_adapter(request.app.state.settings.artifact_storage_path)
    artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == submission_id)
    existing_artifacts = (await session.execute(artifact_stmt)).scalars().all()
    existing_total_bytes = 0
    for artifact in existing_artifacts:
        size = adapter.get_object_size(artifact.storage_key)
        if size is not None:
            existing_total_bytes += size
    try:
        validate_artifact_submission_limits(
            existing_count=len(existing_artifacts),
            existing_total_bytes=existing_total_bytes,
            incoming_sizes=[len(content)],
        )
    except ArtifactLimitError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    try:
        validate_archive_members_safe(content, file.filename or "artifact.bin")
    except ArchiveExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"archive rejected by extraction guard: {exc}",
        ) from exc
    try:
        scan_artifact_or_raise(file.filename or "artifact.bin", content)
    except MalwareScanError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"artifact blocked by malware scanner ({exc.engine}): {exc.reason}",
        ) from exc

    storage_key = adapter.put_object(submission_id, file.filename or "artifact.bin", content)
    content_hash = hashlib.sha256(content).hexdigest()
    challenge_ttl_override = challenge.artifact_ttl_override_seconds if challenge is not None else None
    try:
        expires_at = compute_artifact_expiry(
            created_at=datetime.now(timezone.utc),
            challenge_override_seconds=challenge_ttl_override,
        )
    except ArtifactRetentionPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    artifact = Artifact(
        submission_id=submission_id,
        artifact_type=normalized_type,
        storage_key=storage_key,
        content_hash=content_hash,
        expires_at=expires_at,
    )
    session.add(artifact)
    await increment_quota_usage(
        session,
        quota_user_id=resolve_quota_user_id(request),
        delta=QuotaUsageDelta(artifact_storage_bytes=len(content)),
    )
    await session.commit()
    await session.refresh(artifact)
    return ArtifactUploadResponse.model_validate(artifact, from_attributes=True)


def _is_runnable_artifact(artifact: Artifact) -> bool:
    return artifact.artifact_type in {
        ArtifactType.WEB_BUNDLE,
        ArtifactType.CLI_PACKAGE,
        ArtifactType.API_SERVICE,
        ArtifactType.NOTEBOOK,
    }


def _looks_like_readme(storage_key: str) -> bool:
    filename = storage_key.split("/", 1)[-1]
    if "_" in filename:
        _, filename = filename.split("_", 1)
    return filename.lower().startswith("readme")


def _read_readme_text(adapter: ObjectStorageAdapter, storage_key: str) -> str | None:
    try:
        content = adapter.get_object(storage_key)
    except FileNotFoundError:
        return None
    return content.decode("utf-8", errors="ignore")


def _artifact_download_filename(storage_key: str) -> str:
    filename = storage_key.split("/", 1)[-1]
    if "_" in filename:
        _, filename = filename.split("_", 1)
    return filename or "artifact.bin"


@router.get(
    "/{submission_id}/validation",
    response_model=SubmissionValidationResponse,
)
async def validate_submission_mandatory_requirements(
    submission_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> SubmissionValidationResponse:
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found")

    artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == submission_id)
    artifacts = (await session.execute(artifact_stmt)).scalars().all()
    adapter = build_object_storage_adapter(request.app.state.settings.artifact_storage_path)
    errors: list[str] = []

    errors.extend(validate_measurable_value_hypothesis(submission.value_hypothesis))
    if not any(_is_runnable_artifact(artifact) for artifact in artifacts):
        errors.append("at least one runnable artifact is required")

    readme_artifact = next((artifact for artifact in artifacts if _looks_like_readme(artifact.storage_key)), None)
    if readme_artifact is None:
        errors.append("README artifact is required")
    else:
        readme_text = _read_readme_text(adapter, readme_artifact.storage_key)
        if readme_text is None:
            errors.append("README artifact is required")
        else:
            errors.extend(validate_minimum_readme_content(readme_text))

    return SubmissionValidationResponse(
        submission_id=submission_id,
        valid=len(errors) == 0,
        errors=errors,
    )


@router.post(
    "/{submission_id}/artifacts/{artifact_id}/download-url",
    response_model=ArtifactDownloadURLResponse,
)
async def create_artifact_download_url(
    submission_id: uuid.UUID,
    artifact_id: uuid.UUID,
    payload: ArtifactDownloadURLRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> ArtifactDownloadURLResponse:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None or artifact.submission_id != submission_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    if is_artifact_expired(artifact.expires_at):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="artifact expired by retention policy")

    try:
        token, expires_at = create_artifact_download_token(
            artifact_id=artifact.id,
            submission_id=submission_id,
            ttl_seconds=payload.ttl_seconds,
        )
    except ArtifactPresignError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    base_url = str(request.base_url).rstrip("/")
    download_url = f"{base_url}/submissions/artifacts/{artifact.id}/download?token={token}"
    return ArtifactDownloadURLResponse(
        artifact_id=artifact.id,
        submission_id=submission_id,
        download_url=download_url,
        expires_at=expires_at,
    )


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact_with_token(
    artifact_id: uuid.UUID,
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    if is_artifact_expired(artifact.expires_at):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="artifact expired by retention policy")

    try:
        validate_artifact_download_token(
            token,
            artifact_id=artifact.id,
            submission_id=artifact.submission_id,
        )
    except ArtifactPresignError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    adapter = build_object_storage_adapter(request.app.state.settings.artifact_storage_path)
    try:
        content = adapter.get_object(artifact.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact blob not found") from exc

    filename = _artifact_download_filename(artifact.storage_key)
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename=\"{filename}\"',
            "Cache-Control": "no-store",
        },
    )
