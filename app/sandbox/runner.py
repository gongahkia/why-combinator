from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class SandboxLimits:
    cpu_cores: float
    memory_mb: int
    timeout_seconds: int


@dataclass(frozen=True)
class HackerAgentRunSpec:
    agent_id: str
    image: str
    command: list[str]
    env: dict[str, str]
    task_type: str = "hacker_run"
    trace_id: str = ""


@dataclass(frozen=True)
class HackerAgentRunResult:
    container_name: str
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str
    log_path: str | None


def _load_sandbox_log_max_bytes() -> int:
    return int(os.getenv("SANDBOX_LOG_MAX_BYTES", "131072"))


def _load_sandbox_log_retention_seconds(task_type: str) -> int:
    scoped_key = f"SANDBOX_LOG_RETENTION_{re.sub(r'[^A-Z0-9]+', '_', task_type.upper())}_SECONDS"
    default_seconds = int(os.getenv("SANDBOX_LOG_RETENTION_DEFAULT_SECONDS", "86400"))
    return int(os.getenv(scoped_key, str(default_seconds)))


def _truncate_output(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8", errors="ignore")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return f"{truncated}\n...[truncated due to SANDBOX_LOG_MAX_BYTES={max_bytes}]"


def _redact_sensitive_values(text: str, env: dict[str, str]) -> str:
    redacted = text
    for key, value in env.items():
        if not value:
            continue
        if not any(token in key.upper() for token in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            continue
        redacted = redacted.replace(value, "[REDACTED]")
    return redacted


def _cleanup_expired_logs(log_dir: Path, now: datetime) -> None:
    for log_file in log_dir.glob("*.json"):
        try:
            payload = json.loads(log_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        expires_at_raw = payload.get("expires_at")
        if not isinstance(expires_at_raw, str):
            continue
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
        except ValueError:
            continue
        if expires_at <= now:
            log_file.unlink(missing_ok=True)


def _persist_sandbox_log(
    *,
    container_name: str,
    task_type: str,
    stdout: str,
    stderr: str,
    exit_code: int | None,
    timed_out: bool,
    trace_id: str,
) -> str:
    now = datetime.now(UTC)
    retention_seconds = _load_sandbox_log_retention_seconds(task_type)
    expires_at = now + timedelta(seconds=retention_seconds)
    logs_root = Path(os.getenv("SANDBOX_LOG_DIR", "/tmp/hackathon-sandbox-logs"))
    log_dir = logs_root / task_type
    log_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_expired_logs(log_dir, now)

    log_payload = {
        "container_name": container_name,
        "task_type": task_type,
        "captured_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "timed_out": timed_out,
        "exit_code": exit_code,
        "trace_id": trace_id,
        "stdout": stdout,
        "stderr": stderr,
    }
    log_path = log_dir / f"{container_name}.json"
    log_path.write_text(json.dumps(log_payload, separators=(",", ":")), encoding="utf-8")
    log_path.chmod(0o600)
    return str(log_path)


class HackerAgentRunner:
    def __init__(self, docker_bin: str = "docker") -> None:
        self._docker_bin = docker_bin

    def run(self, spec: HackerAgentRunSpec, limits: SandboxLimits) -> HackerAgentRunResult:
        container_name = f"hacker-agent-{spec.agent_id[:12]}-{uuid.uuid4().hex[:8]}"
        ephemeral_workdir = tempfile.mkdtemp(prefix=f"{container_name}-")
        docker_cmd = [
            self._docker_bin,
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=256m",
            "--mount",
            f"type=bind,src={ephemeral_workdir},dst=/workspace",
            "--workdir",
            "/workspace",
            "--cpus",
            str(limits.cpu_cores),
            "--memory",
            f"{limits.memory_mb}m",
        ]
        for key, value in spec.env.items():
            docker_cmd.extend(["-e", f"{key}={value}"])
        docker_cmd.append(spec.image)
        docker_cmd.extend(spec.command)

        try:
            completed = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=limits.timeout_seconds,
                check=False,
            )
            max_log_bytes = _load_sandbox_log_max_bytes()
            stdout = _redact_sensitive_values(_truncate_output(completed.stdout, max_log_bytes), spec.env)
            stderr = _redact_sensitive_values(_truncate_output(completed.stderr, max_log_bytes), spec.env)
            log_path = _persist_sandbox_log(
                container_name=container_name,
                task_type=spec.task_type,
                stdout=stdout,
                stderr=stderr,
                exit_code=completed.returncode,
                timed_out=False,
                trace_id=spec.trace_id,
            )
            return HackerAgentRunResult(
                container_name=container_name,
                exit_code=completed.returncode,
                timed_out=False,
                stdout=stdout,
                stderr=stderr,
                log_path=log_path,
            )
        except subprocess.TimeoutExpired as exc:
            max_log_bytes = _load_sandbox_log_max_bytes()
            stdout = _redact_sensitive_values(_truncate_output(exc.stdout or "", max_log_bytes), spec.env)
            stderr = _redact_sensitive_values(_truncate_output(exc.stderr or "", max_log_bytes), spec.env)
            log_path = _persist_sandbox_log(
                container_name=container_name,
                task_type=spec.task_type,
                stdout=stdout,
                stderr=stderr,
                exit_code=None,
                timed_out=True,
                trace_id=spec.trace_id,
            )
            return HackerAgentRunResult(
                container_name=container_name,
                exit_code=None,
                timed_out=True,
                stdout=stdout,
                stderr=stderr,
                log_path=log_path,
            )
        finally:
            shutil.rmtree(ephemeral_workdir, ignore_errors=True)


def load_hacker_runner_limits_from_env() -> SandboxLimits:
    return SandboxLimits(
        cpu_cores=float(os.getenv("HACKER_RUNNER_CPU_CORES", "1.0")),
        memory_mb=int(os.getenv("HACKER_RUNNER_MEMORY_MB", "1024")),
        timeout_seconds=int(os.getenv("HACKER_RUNNER_TIMEOUT_SECONDS", "300")),
    )
