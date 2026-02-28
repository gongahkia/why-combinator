from __future__ import annotations

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
class NotebookRuntimeValidationResult:
    submission_id: uuid.UUID
    outcome: RuntimeValidationOutcome
    exit_code: int | None
    stdout: str
    stderr: str


async def run_notebook_runtime_validator_subagent(
    session: AsyncSession,
    submission_id: uuid.UUID,
    storage_root: str,
    timeout_seconds: int = 300,
) -> NotebookRuntimeValidationResult:
    artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(
        Artifact.submission_id == submission_id,
        Artifact.artifact_type == ArtifactType.NOTEBOOK,
    )
    notebook_artifact = (await session.execute(artifact_stmt)).scalars().first()
    if notebook_artifact is None:
        await apply_runtime_validation_outcome(session, submission_id, "skipped")
        return NotebookRuntimeValidationResult(
            submission_id=submission_id,
            outcome="skipped",
            exit_code=None,
            stdout="",
            stderr="notebook artifact missing",
        )

    artifact_path = Path(storage_root) / notebook_artifact.storage_key
    if not artifact_path.exists():
        await apply_runtime_validation_outcome(session, submission_id, "failed")
        return NotebookRuntimeValidationResult(
            submission_id=submission_id,
            outcome="failed",
            exit_code=None,
            stdout="",
            stderr="notebook artifact blob not found",
        )

    executed_notebook = artifact_path.parent / f"executed_{artifact_path.name}"
    try:
        completed = subprocess.run(
            ["papermill", str(artifact_path), str(executed_notebook)],
            cwd=artifact_path.parent,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        outcome: RuntimeValidationOutcome = "passed" if completed.returncode == 0 else "failed"
        await apply_runtime_validation_outcome(session, submission_id, outcome)
        return NotebookRuntimeValidationResult(
            submission_id=submission_id,
            outcome=outcome,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        await apply_runtime_validation_outcome(session, submission_id, "failed")
        return NotebookRuntimeValidationResult(
            submission_id=submission_id,
            outcome="failed",
            exit_code=None,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + "\nnotebook execution timed out",
        )
