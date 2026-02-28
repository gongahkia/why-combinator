from __future__ import annotations

import shlex
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ArtifactType
from app.db.models import Artifact
from app.validation.runtime import RuntimeValidationOutcome, apply_runtime_validation_outcome


@dataclass(frozen=True)
class RuntimeValidationResult:
    submission_id: uuid.UUID
    outcome: RuntimeValidationOutcome
    exit_code: int | None
    stdout: str
    stderr: str


async def run_cli_runtime_validator_subagent(
    session: AsyncSession,
    submission_id: uuid.UUID,
    storage_root: str,
    declared_command: str | None,
    timeout_seconds: int = 60,
) -> RuntimeValidationResult:
    artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(
        Artifact.submission_id == submission_id,
        Artifact.artifact_type == ArtifactType.CLI_PACKAGE,
    )
    cli_artifact = (await session.execute(artifact_stmt)).scalars().first()
    if cli_artifact is None or declared_command is None or not declared_command.strip():
        await apply_runtime_validation_outcome(session, submission_id, "skipped")
        return RuntimeValidationResult(
            submission_id=submission_id,
            outcome="skipped",
            exit_code=None,
            stdout="",
            stderr="cli artifact or declared command missing",
        )

    artifact_path = Path(storage_root) / cli_artifact.storage_key
    if not artifact_path.exists():
        await apply_runtime_validation_outcome(session, submission_id, "failed")
        return RuntimeValidationResult(
            submission_id=submission_id,
            outcome="failed",
            exit_code=None,
            stdout="",
            stderr="cli artifact blob not found",
        )

    try:
        completed = subprocess.run(
            shlex.split(declared_command),
            cwd=artifact_path.parent,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        outcome: RuntimeValidationOutcome = "passed" if completed.returncode == 0 else "failed"
        await apply_runtime_validation_outcome(session, submission_id, outcome)
        return RuntimeValidationResult(
            submission_id=submission_id,
            outcome=outcome,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        await apply_runtime_validation_outcome(session, submission_id, "failed")
        return RuntimeValidationResult(
            submission_id=submission_id,
            outcome="failed",
            exit_code=None,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + "\ncommand timed out",
        )
