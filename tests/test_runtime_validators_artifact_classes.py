from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, ArtifactType, RunState, SubmissionState
from app.db.models import Agent, Artifact, Challenge, Run, Submission
from app.validation.runtime_api import run_api_runtime_validator_subagent
from app.validation.runtime_cli import run_cli_runtime_validator_subagent
from app.validation.runtime_notebook import run_notebook_runtime_validator_subagent
from app.validation.runtime_web import run_web_runtime_validator_subagent


@pytest.mark.asyncio
async def test_runtime_validators_cover_cli_api_web_and_notebook_artifact_classes(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    challenge = Challenge(
        title="Runtime validator coverage test",
        prompt="Validate runtime behavior for multiple artifact classes.",
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

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="runtime-agent")
    session.add(agent)
    await session.flush()

    async def _submission_with_missing_blob(artifact_type: ArtifactType, storage_key: str) -> Submission:
        submission = Submission(
            run_id=run.id,
            agent_id=agent.id,
            state=SubmissionState.PENDING,
            value_hypothesis=f"Hypothesis for {artifact_type.value}",
            summary=f"Summary for {artifact_type.value}",
        )
        session.add(submission)
        await session.flush()
        session.add(
            Artifact(
                submission_id=submission.id,
                artifact_type=artifact_type,
                storage_key=storage_key,
                content_hash="0" * 64,
            )
        )
        await session.commit()
        return submission

    cli_submission = await _submission_with_missing_blob(ArtifactType.CLI_PACKAGE, "cli/tool.tar.gz")
    cli_result = await run_cli_runtime_validator_subagent(
        session,
        cli_submission.id,
        storage_root=str(tmp_path),
        declared_command="echo hello",
    )
    assert cli_result.outcome == "failed"
    assert "blob not found" in cli_result.stderr
    await session.refresh(cli_submission)
    assert cli_submission.human_testing_required is True

    api_submission = await _submission_with_missing_blob(ArtifactType.API_SERVICE, "api/service.tar.gz")
    api_result = await run_api_runtime_validator_subagent(
        session,
        api_submission.id,
        storage_root=str(tmp_path),
        boot_command="python3 -m http.server",
    )
    assert api_result.outcome == "failed"
    assert "blob not found" in api_result.stderr
    await session.refresh(api_submission)
    assert api_submission.human_testing_required is True

    web_submission = await _submission_with_missing_blob(ArtifactType.WEB_BUNDLE, "web/index.html")
    web_result = await run_web_runtime_validator_subagent(
        session,
        web_submission.id,
        storage_root=str(tmp_path),
    )
    assert web_result.outcome == "failed"
    assert "blob not found" in web_result.stderr
    await session.refresh(web_submission)
    assert web_submission.human_testing_required is True

    notebook_submission = await _submission_with_missing_blob(ArtifactType.NOTEBOOK, "notebooks/demo.ipynb")
    notebook_result = await run_notebook_runtime_validator_subagent(
        session,
        notebook_submission.id,
        storage_root=str(tmp_path),
    )
    assert notebook_result.outcome == "failed"
    assert "blob not found" in notebook_result.stderr
    await session.refresh(notebook_submission)
    assert notebook_submission.human_testing_required is True
