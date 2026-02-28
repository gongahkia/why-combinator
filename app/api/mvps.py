from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.enums import SubmissionState
from app.db.models import Artifact, Run, Submission

router = APIRouter(tags=["artifacts"])


class MVPArtifactDownload(BaseModel):
    artifact_id: uuid.UUID
    artifact_type: str
    storage_key: str
    content_hash: str
    download_url: str


class MVPBundleItem(BaseModel):
    submission_id: uuid.UUID
    agent_id: uuid.UUID
    accepted_at: datetime | None
    artifacts: list[MVPArtifactDownload]


class MVPBundlesResponse(BaseModel):
    run_id: uuid.UUID
    bundles: list[MVPBundleItem]


@router.get("/runs/{run_id}/mvp-bundles", response_model=MVPBundlesResponse)
async def get_mvp_bundles(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> MVPBundlesResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    submission_stmt: Select[tuple[Submission]] = select(Submission).where(
        Submission.run_id == run_id,
        Submission.state == SubmissionState.ACCEPTED,
    )
    submissions = (await session.execute(submission_stmt)).scalars().all()

    bundles: list[MVPBundleItem] = []
    for submission in submissions:
        artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == submission.id)
        artifacts = (await session.execute(artifact_stmt)).scalars().all()
        bundles.append(
            MVPBundleItem(
                submission_id=submission.id,
                agent_id=submission.agent_id,
                accepted_at=submission.accepted_at,
                artifacts=[
                    MVPArtifactDownload(
                        artifact_id=artifact.id,
                        artifact_type=str(artifact.artifact_type),
                        storage_key=artifact.storage_key,
                        content_hash=artifact.content_hash,
                        download_url=f"/artifacts/{artifact.id}/download",
                    )
                    for artifact in artifacts
                ],
            )
        )

    return MVPBundlesResponse(run_id=run_id, bundles=bundles)


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")

    artifact_path = Path(request.app.state.settings.artifact_storage_path) / artifact.storage_key
    if not artifact_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact blob not found")
    filename = artifact_path.name.split("_", 1)[-1]
    return FileResponse(path=artifact_path, filename=filename)
