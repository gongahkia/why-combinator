from __future__ import annotations

import shlex
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ArtifactType
from app.db.models import Artifact
from app.validation.runtime import RuntimeValidationOutcome, apply_runtime_validation_outcome


@dataclass(frozen=True)
class APIRuntimeValidationResult:
    submission_id: uuid.UUID
    outcome: RuntimeValidationOutcome
    http_status: int | None
    stdout: str
    stderr: str


async def run_api_runtime_validator_subagent(
    session: AsyncSession,
    submission_id: uuid.UUID,
    storage_root: str,
    boot_command: str | None,
    healthcheck_url: str = "http://127.0.0.1:8000/health",
    boot_wait_seconds: int = 3,
    probe_timeout_seconds: int = 5,
) -> APIRuntimeValidationResult:
    artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(
        Artifact.submission_id == submission_id,
        Artifact.artifact_type == ArtifactType.API_SERVICE,
    )
    api_artifact = (await session.execute(artifact_stmt)).scalars().first()
    if api_artifact is None or boot_command is None or not boot_command.strip():
        await apply_runtime_validation_outcome(session, submission_id, "skipped")
        return APIRuntimeValidationResult(
            submission_id=submission_id,
            outcome="skipped",
            http_status=None,
            stdout="",
            stderr="api artifact or boot command missing",
        )

    artifact_path = Path(storage_root) / api_artifact.storage_key
    if not artifact_path.exists():
        await apply_runtime_validation_outcome(session, submission_id, "failed")
        return APIRuntimeValidationResult(
            submission_id=submission_id,
            outcome="failed",
            http_status=None,
            stdout="",
            stderr="api artifact blob not found",
        )

    process = subprocess.Popen(  # noqa: S603
        shlex.split(boot_command),
        cwd=artifact_path.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(boot_wait_seconds)
        request = urllib.request.Request(healthcheck_url, method="GET")
        with urllib.request.urlopen(request, timeout=probe_timeout_seconds) as response:  # noqa: S310
            status_code = response.getcode()
        outcome: RuntimeValidationOutcome = "passed" if status_code == 200 else "failed"
        await apply_runtime_validation_outcome(session, submission_id, outcome)
        return APIRuntimeValidationResult(
            submission_id=submission_id,
            outcome=outcome,
            http_status=status_code,
            stdout="",
            stderr="",
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        await apply_runtime_validation_outcome(session, submission_id, "failed")
        return APIRuntimeValidationResult(
            submission_id=submission_id,
            outcome="failed",
            http_status=None,
            stdout="",
            stderr=f"health probe failed: {exc}",
        )
    finally:
        process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
