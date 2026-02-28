from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.artifacts import validate_submission_mandatory_requirements
from app.db.enums import AgentRole, ArtifactType, RunState, SubmissionState
from app.db.models import Agent, Artifact, Challenge, Run, Submission
from app.validation.value_hypothesis import validate_measurable_value_hypothesis


def test_value_hypothesis_validator_accepts_measurable_statement() -> None:
    hypothesis = "Reduce incident acknowledgment time by 30% within 2 weeks."
    assert validate_measurable_value_hypothesis(hypothesis) == []


def test_value_hypothesis_validator_rejects_non_measurable_statement() -> None:
    hypothesis = "Build a better workflow for engineers."
    errors = validate_measurable_value_hypothesis(hypothesis)
    assert len(errors) == 1
    assert "measurable outcome" in errors[0]


@pytest.mark.asyncio
async def test_submission_validation_reports_non_measurable_value_hypothesis(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    challenge = Challenge(
        title="Value hypothesis validator test",
        prompt="Enforce measurable value hypothesis statements.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="hypothesis-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Build a better workflow for engineers.",
        summary="Submission with non-measurable value hypothesis.",
    )
    session.add(submission)
    await session.flush()

    readme_storage_key = "submissions/README.md"
    readme_path = tmp_path / readme_storage_key
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(
        "# Overview\nText\n\n## Setup\nInstall dependencies.\n\n## Usage\nRun the service.\n"
    )

    session.add(
        Artifact(
            submission_id=submission.id,
            artifact_type=ArtifactType.CLI_PACKAGE,
            storage_key=readme_storage_key,
            content_hash="2" * 64,
        )
    )
    await session.commit()

    fake_request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(artifact_storage_path=str(tmp_path))))
    )
    result = await validate_submission_mandatory_requirements(submission.id, fake_request, session)

    assert result.valid is False
    assert "value_hypothesis must describe a measurable outcome" in " ".join(result.errors)
