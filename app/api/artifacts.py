from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.enums import ArtifactType
from app.db.models import Artifact, Submission
from app.storage.local import LocalObjectStorageAdapter

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

    adapter = LocalObjectStorageAdapter(request.app.state.settings.artifact_storage_path)
    storage_key = adapter.put_object(submission_id, file.filename or "artifact.bin", content)
    content_hash = hashlib.sha256(content).hexdigest()
    artifact = Artifact(
        submission_id=submission_id,
        artifact_type=normalized_type,
        storage_key=storage_key,
        content_hash=content_hash,
    )
    session.add(artifact)
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


def _is_short_readme(path: Path, max_chars: int = 3000) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    return bool(text) and len(text) <= max_chars


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
    errors: list[str] = []

    if not submission.value_hypothesis.strip():
        errors.append("value_hypothesis is required")
    if not any(_is_runnable_artifact(artifact) for artifact in artifacts):
        errors.append("at least one runnable artifact is required")

    readme_artifact = next((artifact for artifact in artifacts if _looks_like_readme(artifact.storage_key)), None)
    if readme_artifact is None:
        errors.append("README artifact is required")
    else:
        readme_path = Path(request.app.state.settings.artifact_storage_path) / readme_artifact.storage_key
        if not _is_short_readme(readme_path):
            errors.append("README artifact must be non-empty and at most 3000 characters")

    return SubmissionValidationResponse(
        submission_id=submission_id,
        valid=len(errors) == 0,
        errors=errors,
    )
