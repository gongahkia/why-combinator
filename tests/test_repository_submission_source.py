from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.submissions import RepositorySubmissionSourceRequest, attach_repository_submission_source
from app.db.enums import AgentRole, ArtifactType, RunState
from app.db.models import Agent, Artifact, Challenge, Run, Submission


@dataclass
class _CheckoutResult:
    checkout_path: str
    commit: str


@pytest.mark.asyncio
async def test_repository_submission_source_creates_submission_artifact_and_enqueues_job(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenge = Challenge(
        title="Repository source challenge",
        prompt="Build an MVP from a pinned repository commit.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.6,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="repo-agent")
    session.add(agent)
    await session.commit()

    fake_request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(artifact_storage_path="/tmp/artifacts")))
    )

    monkeypatch.setattr(
        "app.api.submissions.isolated_git_checkout",
        lambda **_: _CheckoutResult(
            checkout_path="/tmp/artifacts/repo-checkouts/repo-artifact-abc123",
            commit="a" * 40,
        ),
    )

    enqueue_calls: list[tuple[str, str]] = []

    def _fake_enqueue(submission_id, checkpoint_id: str) -> dict[str, str]:
        enqueue_calls.append((str(submission_id), checkpoint_id))
        return {
            "job_type": "score-submission",
            "submission_id": str(submission_id),
            "checkpoint_id": checkpoint_id,
            "status": "queued",
            "trace_id": "trace-test",
        }

    monkeypatch.setattr("app.api.submissions.enqueue_submission_score_job", _fake_enqueue)

    response = await attach_repository_submission_source(
        run.id,
        RepositorySubmissionSourceRequest(
            agent_id=agent.id,
            value_hypothesis="A pinned source checkout improves reproducibility and ingest reliability.",
            repository_url="https://github.com/example/project.git",
            commit="a" * 40,
        ),
        request=fake_request,
        session=session,
    )

    assert response.submission.run_id == run.id
    assert response.submission.agent_id == agent.id
    assert response.resolved_commit == "a" * 40
    assert response.ingestion_job["status"] == "queued"
    assert response.ingestion_job["checkpoint_id"] == "repository_ingest"
    assert enqueue_calls == [(str(response.submission.id), "repository_ingest")]

    persisted_submission = await session.get(Submission, response.submission.id)
    assert persisted_submission is not None

    persisted_artifact = await session.get(Artifact, response.artifact_id)
    assert persisted_artifact is not None
    assert persisted_artifact.submission_id == response.submission.id
    assert persisted_artifact.artifact_type == ArtifactType.CLI_PACKAGE
    assert persisted_artifact.storage_key == "repo-checkouts/repo-artifact-abc123"

    artifacts_for_submission = await session.scalars(select(Artifact).where(Artifact.submission_id == response.submission.id))
    assert len(list(artifacts_for_submission)) == 1
