from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.enums import ArtifactType
from app.db.models import Artifact, Submission
from app.storage.local import LocalObjectStorageAdapter

router = APIRouter(prefix="/submissions", tags=["artifacts"])


class ArtifactUploadResponse(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    artifact_type: ArtifactType
    storage_key: str
    content_hash: str
    created_at: datetime
    updated_at: datetime


@router.post(
    "/{submission_id}/artifacts",
    status_code=status.HTTP_201_CREATED,
    response_model=ArtifactUploadResponse,
)
async def upload_artifact(
    submission_id: uuid.UUID,
    request: Request,
    artifact_type: ArtifactType,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> ArtifactUploadResponse:
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="submission not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="artifact file is empty")

    adapter = LocalObjectStorageAdapter(request.app.state.settings.artifact_storage_path)
    storage_key = adapter.put_object(submission_id, file.filename or "artifact.bin", content)
    content_hash = hashlib.sha256(content).hexdigest()
    artifact = Artifact(
        submission_id=submission_id,
        artifact_type=artifact_type,
        storage_key=storage_key,
        content_hash=content_hash,
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    return ArtifactUploadResponse.model_validate(artifact, from_attributes=True)
