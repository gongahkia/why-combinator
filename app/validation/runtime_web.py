from __future__ import annotations

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
class WebRuntimeValidationResult:
    submission_id: uuid.UUID
    outcome: RuntimeValidationOutcome
    http_status: int | None
    console_error_count: int
    stderr: str


def _scan_console_error_markers(web_root: Path) -> int:
    error_count = 0
    for file_path in web_root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in {".js", ".ts", ".jsx", ".tsx", ".html"}:
            continue
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        error_count += text.count("console.error(")
    return error_count


async def run_web_runtime_validator_subagent(
    session: AsyncSession,
    submission_id: uuid.UUID,
    storage_root: str,
    port: int = 8765,
    probe_timeout_seconds: int = 5,
) -> WebRuntimeValidationResult:
    artifact_stmt: Select[tuple[Artifact]] = select(Artifact).where(
        Artifact.submission_id == submission_id,
        Artifact.artifact_type == ArtifactType.WEB_BUNDLE,
    )
    web_artifact = (await session.execute(artifact_stmt)).scalars().first()
    if web_artifact is None:
        await apply_runtime_validation_outcome(session, submission_id, "skipped")
        return WebRuntimeValidationResult(
            submission_id=submission_id,
            outcome="skipped",
            http_status=None,
            console_error_count=0,
            stderr="web artifact missing",
        )

    artifact_path = Path(storage_root) / web_artifact.storage_key
    if not artifact_path.exists():
        await apply_runtime_validation_outcome(session, submission_id, "failed")
        return WebRuntimeValidationResult(
            submission_id=submission_id,
            outcome="failed",
            http_status=None,
            console_error_count=0,
            stderr="web artifact blob not found",
        )

    serve_root = artifact_path.parent
    process = subprocess.Popen(  # noqa: S603
        ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=serve_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(2)
        request = urllib.request.Request(f"http://127.0.0.1:{port}/", method="GET")
        with urllib.request.urlopen(request, timeout=probe_timeout_seconds) as response:  # noqa: S310
            status_code = response.getcode()
        console_error_count = _scan_console_error_markers(serve_root)
        outcome: RuntimeValidationOutcome = "passed" if status_code == 200 and console_error_count == 0 else "failed"
        await apply_runtime_validation_outcome(session, submission_id, outcome)
        return WebRuntimeValidationResult(
            submission_id=submission_id,
            outcome=outcome,
            http_status=status_code,
            console_error_count=console_error_count,
            stderr="",
        )
    except urllib.error.URLError as exc:
        await apply_runtime_validation_outcome(session, submission_id, "failed")
        return WebRuntimeValidationResult(
            submission_id=submission_id,
            outcome="failed",
            http_status=None,
            console_error_count=0,
            stderr=f"web probe failed: {exc}",
        )
    finally:
        process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
