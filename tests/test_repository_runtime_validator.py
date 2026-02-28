from __future__ import annotations

import subprocess

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, ArtifactType, RunState, SubmissionState
from app.db.models import Agent, Artifact, Challenge, Run, Submission
from app.validation.runtime_repository import (
    SAFE_REPOSITORY_TEST_COMMANDS,
    detect_repository_project_type,
    run_repository_runtime_validator_subagent,
)


async def _create_submission_with_repository_artifact(
    session: AsyncSession,
    storage_key: str,
) -> Submission:
    challenge = Challenge(
        title="Repository runtime validation challenge",
        prompt="Validate repository runtime checks.",
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

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="repo-runtime-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Repository runtime validation should exercise safe test commands.",
        summary="Repository runtime validation submission.",
    )
    session.add(submission)
    await session.flush()

    session.add(
        Artifact(
            submission_id=submission.id,
            artifact_type=ArtifactType.CLI_PACKAGE,
            storage_key=storage_key,
            content_hash="a" * 64,
        )
    )
    await session.commit()
    return submission


@pytest.mark.asyncio
async def test_repository_runtime_validator_detects_python_and_runs_safe_command(
    session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_root = tmp_path / "repo-checkouts" / "repo-python"
    repository_root.mkdir(parents=True)
    (repository_root / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.1.0'\n")
    submission = await _create_submission_with_repository_artifact(
        session,
        storage_key="repo-checkouts/repo-python",
    )

    observed: dict[str, object] = {}

    def _fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["cwd"] = kwargs["cwd"]
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("app.validation.runtime_repository.subprocess.run", _fake_run)

    result = await run_repository_runtime_validator_subagent(
        session,
        submission.id,
        storage_root=str(tmp_path),
    )

    assert result.outcome == "passed"
    assert result.project_type == "python"
    assert result.safe_command == list(SAFE_REPOSITORY_TEST_COMMANDS["python"])
    assert observed["command"] == list(SAFE_REPOSITORY_TEST_COMMANDS["python"])
    assert observed["cwd"] == repository_root
    await session.refresh(submission)
    assert submission.human_testing_required is False


@pytest.mark.asyncio
async def test_repository_runtime_validator_skips_unknown_project_type(
    session: AsyncSession,
    tmp_path,
) -> None:
    repository_root = tmp_path / "repo-checkouts" / "repo-unknown"
    repository_root.mkdir(parents=True)
    (repository_root / "README.txt").write_text("no detectable project markers")
    submission = await _create_submission_with_repository_artifact(
        session,
        storage_key="repo-checkouts/repo-unknown",
    )

    result = await run_repository_runtime_validator_subagent(
        session,
        submission.id,
        storage_root=str(tmp_path),
    )

    assert result.outcome == "skipped"
    assert result.project_type == "unknown"
    assert result.safe_command == []
    assert "could not be determined" in result.stderr
    await session.refresh(submission)
    assert submission.human_testing_required is True


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        ("pyproject.toml", "python"),
        ("package.json", "node"),
        ("go.mod", "go"),
        ("Cargo.toml", "rust"),
    ],
)
def test_detect_repository_project_type_from_marker_files(
    tmp_path,
    marker: str,
    expected: str,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    (repository_root / marker).write_text("marker")

    detected = detect_repository_project_type(repository_root)

    assert detected == expected
