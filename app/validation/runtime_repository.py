from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ArtifactType
from app.db.models import Artifact
from app.validation.runtime import RuntimeValidationOutcome, apply_runtime_validation_outcome


RepositoryProjectType = Literal["python", "node", "go", "rust", "unknown"]

SAFE_REPOSITORY_TEST_COMMANDS: dict[str, tuple[str, ...]] = {
    "python": ("python3", "-m", "pytest", "-q", "--maxfail=1"),
    "node": ("node", "--test"),
    "go": ("go", "test", "./..."),
    "rust": ("cargo", "test", "--locked", "--quiet"),
}


@dataclass(frozen=True)
class RepositoryRuntimeValidationResult:
    submission_id: uuid.UUID
    outcome: RuntimeValidationOutcome
    project_type: RepositoryProjectType
    safe_command: list[str]
    exit_code: int | None
    stdout: str
    stderr: str


def detect_repository_project_type(repository_root: Path) -> RepositoryProjectType:
    if any((repository_root / marker).exists() for marker in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg")):
        return "python"
    if (repository_root / "package.json").exists():
        return "node"
    if (repository_root / "go.mod").exists():
        return "go"
    if (repository_root / "Cargo.toml").exists():
        return "rust"
    return "unknown"


def resolve_safe_repository_test_command(project_type: RepositoryProjectType) -> tuple[str, ...] | None:
    return SAFE_REPOSITORY_TEST_COMMANDS.get(project_type)


def _resolve_repository_root(storage_root: str, storage_key: str) -> Path:
    artifact_path = Path(storage_key)
    if artifact_path.is_absolute():
        return artifact_path
    return Path(storage_root) / storage_key


async def run_repository_runtime_validator_subagent(
    session: AsyncSession,
    submission_id: uuid.UUID,
    storage_root: str,
    timeout_seconds: int = 120,
) -> RepositoryRuntimeValidationResult:
    artifact_stmt: Select[tuple[Artifact]] = (
        select(Artifact)
        .where(
            Artifact.submission_id == submission_id,
            Artifact.artifact_type == ArtifactType.CLI_PACKAGE,
        )
        .order_by(Artifact.created_at.desc())
    )
    artifacts = (await session.execute(artifact_stmt)).scalars().all()
    repository_root = next(
        (
            candidate
            for artifact in artifacts
            if (candidate := _resolve_repository_root(storage_root, artifact.storage_key)).exists() and candidate.is_dir()
        ),
        None,
    )
    if repository_root is None:
        await apply_runtime_validation_outcome(session, submission_id, "skipped")
        return RepositoryRuntimeValidationResult(
            submission_id=submission_id,
            outcome="skipped",
            project_type="unknown",
            safe_command=[],
            exit_code=None,
            stdout="",
            stderr="repository artifact directory not found",
        )

    project_type = detect_repository_project_type(repository_root)
    safe_command = resolve_safe_repository_test_command(project_type)
    if safe_command is None:
        await apply_runtime_validation_outcome(session, submission_id, "skipped")
        return RepositoryRuntimeValidationResult(
            submission_id=submission_id,
            outcome="skipped",
            project_type=project_type,
            safe_command=[],
            exit_code=None,
            stdout="",
            stderr="repository project type could not be determined",
        )

    try:
        completed = subprocess.run(  # noqa: S603
            list(safe_command),
            cwd=repository_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        outcome: RuntimeValidationOutcome = "passed" if completed.returncode == 0 else "failed"
        await apply_runtime_validation_outcome(session, submission_id, outcome)
        return RepositoryRuntimeValidationResult(
            submission_id=submission_id,
            outcome=outcome,
            project_type=project_type,
            safe_command=list(safe_command),
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        await apply_runtime_validation_outcome(session, submission_id, "failed")
        return RepositoryRuntimeValidationResult(
            submission_id=submission_id,
            outcome="failed",
            project_type=project_type,
            safe_command=list(safe_command),
            exit_code=None,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + "\nrepository runtime validation timed out",
        )
    except OSError as exc:
        await apply_runtime_validation_outcome(session, submission_id, "failed")
        return RepositoryRuntimeValidationResult(
            submission_id=submission_id,
            outcome="failed",
            project_type=project_type,
            safe_command=list(safe_command),
            exit_code=None,
            stdout="",
            stderr=f"repository test command could not be executed: {exc}",
        )
