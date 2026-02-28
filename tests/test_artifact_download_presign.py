from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.api.artifacts import (
    ArtifactDownloadURLRequest,
    create_artifact_download_url,
    download_artifact_with_token,
    upload_artifact,
)
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Artifact, Challenge, Run, Submission
from app.storage.presign import ArtifactPresignError, create_artifact_download_token, validate_artifact_download_token


@pytest.mark.asyncio
async def test_artifact_download_url_and_scope_constraints(session: AsyncSession, tmp_path) -> None:
    challenge = Challenge(
        title="Presign challenge",
        prompt="Issue short-lived artifact download URLs.",
        iteration_window_seconds=900,
        minimum_quality_threshold=0.2,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="download-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Presigned URL access should be constrained by artifact and expiry.",
        summary="Presign download submission.",
    )
    session.add(submission)
    await session.commit()

    fake_request = SimpleNamespace(
        base_url="http://testserver/",
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(artifact_storage_path=str(tmp_path)))),
    )

    await upload_artifact(
        submission_id=submission.id,
        request=fake_request,
        artifact_type="cli_package",
        file=UploadFile(filename="alpha.txt", file=BytesIO(b"alpha-content")),
        session=session,
    )
    await upload_artifact(
        submission_id=submission.id,
        request=fake_request,
        artifact_type="cli_package",
        file=UploadFile(filename="beta.txt", file=BytesIO(b"beta-content")),
        session=session,
    )

    artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == submission.id).order_by(Artifact.created_at.asc())
    artifacts = (await session.execute(artifact_stmt)).scalars().all()
    first_artifact, second_artifact = artifacts

    before = datetime.now(UTC)
    url_response = await create_artifact_download_url(
        submission_id=submission.id,
        artifact_id=first_artifact.id,
        payload=ArtifactDownloadURLRequest(ttl_seconds=9999),
        request=fake_request,
        session=session,
    )
    after = datetime.now(UTC)

    parsed = urlparse(url_response.download_url)
    token = parse_qs(parsed.query)["token"][0]
    assert url_response.download_url.startswith("http://testserver/submissions/artifacts/")
    assert timedelta(seconds=0) < (url_response.expires_at - before) <= timedelta(seconds=905)
    assert url_response.expires_at >= after

    download_response = await download_artifact_with_token(
        artifact_id=first_artifact.id,
        token=token,
        request=fake_request,
        session=session,
    )
    assert download_response.body == b"alpha-content"
    assert download_response.headers["Cache-Control"] == "no-store"

    with pytest.raises(HTTPException) as exc_info:
        await download_artifact_with_token(
            artifact_id=second_artifact.id,
            token=token,
            request=fake_request,
            session=session,
        )
    assert exc_info.value.status_code == 403


def test_artifact_presign_token_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_DOWNLOAD_URL_MAX_TTL_SECONDS", "60")
    now = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    artifact_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    submission_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    token, expires_at = create_artifact_download_token(
        artifact_id,
        submission_id,
        ttl_seconds=600,
        now=now,
    )
    assert expires_at == now + timedelta(seconds=60)

    with pytest.raises(ArtifactPresignError, match="expired"):
        validate_artifact_download_token(
            token,
            artifact_id=artifact_id,
            submission_id=submission_id,
            now=now + timedelta(seconds=61),
        )
