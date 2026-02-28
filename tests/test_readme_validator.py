from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.artifacts import validate_submission_mandatory_requirements
from app.db.enums import AgentRole, ArtifactType, RunState, SubmissionState
from app.db.models import Agent, Artifact, Challenge, Run, Submission
from app.validation.readme import validate_minimum_readme_content


def test_readme_parser_accepts_required_sections() -> None:
    text = """
    # Overview
    Builds a runnable MVP.

    ## Setup
    Install dependencies.

    ## Usage
    Run the CLI command.
    """
    assert validate_minimum_readme_content(text) == []


def test_readme_parser_rejects_missing_sections() -> None:
    text = """
    # Overview
    MVP description only.
    """
    errors = validate_minimum_readme_content(text)
    assert len(errors) == 1
    assert "missing required sections" in errors[0]
    assert "setup" in errors[0]
    assert "usage" in errors[0]


@pytest.mark.asyncio
async def test_submission_validation_reports_missing_readme_sections(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    challenge = Challenge(
        title="README section validator test",
        prompt="Ensure README parser enforces required sections.",
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

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="readme-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="README structure improves reviewability.",
        summary="README validator submission.",
    )
    session.add(submission)
    await session.flush()

    readme_storage_key = "submissions/readme.md"
    readme_path = tmp_path / readme_storage_key
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text("# Overview\nOnly one section is present.\n")

    session.add(
        Artifact(
            submission_id=submission.id,
            artifact_type=ArtifactType.CLI_PACKAGE,
            storage_key=readme_storage_key,
            content_hash="1" * 64,
        )
    )
    await session.commit()

    fake_request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(artifact_storage_path=str(tmp_path))))
    )
    result = await validate_submission_mandatory_requirements(submission.id, fake_request, session)

    assert result.valid is False
    assert any("missing required sections" in error for error in result.errors)
