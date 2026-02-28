from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace

import pytest
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.api.artifacts import upload_artifact
from app.artifacts.retention import (
    ArtifactRetentionPolicyError,
    compute_artifact_expiry,
    resolve_artifact_retention_ttl_seconds,
)
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Artifact, Challenge, Run, Submission


def test_resolve_artifact_retention_ttl_prefers_challenge_override() -> None:
    assert resolve_artifact_retention_ttl_seconds(1800) == 1800


@pytest.mark.parametrize("ttl", [0, -1, 31_536_001])
def test_resolve_artifact_retention_ttl_rejects_invalid_values(ttl: int) -> None:
    with pytest.raises(ArtifactRetentionPolicyError):
        resolve_artifact_retention_ttl_seconds(ttl)


def test_compute_artifact_expiry_uses_default_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTIFACT_RETENTION_DEFAULT_TTL_SECONDS", "600")
    created_at = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)

    expires_at = compute_artifact_expiry(created_at=created_at, challenge_override_seconds=None)

    assert expires_at == created_at + timedelta(seconds=600)


@pytest.mark.asyncio
async def test_upload_artifact_applies_challenge_ttl_override(session: AsyncSession, tmp_path) -> None:
    challenge = Challenge(
        title="Retention challenge",
        prompt="Ensure artifact retention can be overridden per challenge.",
        iteration_window_seconds=1200,
        minimum_quality_threshold=0.2,
        risk_appetite="balanced",
        complexity_slider=0.5,
        artifact_ttl_override_seconds=1800,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="retention-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Retention policy should set per-artifact expiry timestamps.",
        summary="Retention test submission.",
    )
    session.add(submission)
    await session.commit()

    fake_request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(artifact_storage_path=str(tmp_path))))
    )

    before = datetime.now(UTC)
    await upload_artifact(
        submission_id=submission.id,
        request=fake_request,
        artifact_type="cli_package",
        file=UploadFile(filename="run.sh", file=BytesIO(b"#!/bin/sh\necho hi\n")),
        session=session,
    )
    after = datetime.now(UTC)

    artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(Artifact.submission_id == submission.id)
    persisted_artifact = (await session.execute(artifact_stmt)).scalars().first()
    if persisted_artifact is None:
        raise AssertionError("artifact was not persisted")

    assert persisted_artifact.expires_at is not None
    expires_at = (
        persisted_artifact.expires_at
        if persisted_artifact.expires_at.tzinfo is not None
        else persisted_artifact.expires_at.replace(tzinfo=UTC)
    )
    earliest_expected = before + timedelta(seconds=1795)
    latest_expected = after + timedelta(seconds=1805)
    assert earliest_expected <= expires_at <= latest_expected
