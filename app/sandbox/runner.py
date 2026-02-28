from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass


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


@dataclass(frozen=True)
class HackerAgentRunResult:
    container_name: str
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str


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
            return HackerAgentRunResult(
                container_name=container_name,
                exit_code=completed.returncode,
                timed_out=False,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        except subprocess.TimeoutExpired as exc:
            return HackerAgentRunResult(
                container_name=container_name,
                exit_code=None,
                timed_out=True,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
            )
        finally:
            shutil.rmtree(ephemeral_workdir, ignore_errors=True)


def load_hacker_runner_limits_from_env() -> SandboxLimits:
    return SandboxLimits(
        cpu_cores=float(os.getenv("HACKER_RUNNER_CPU_CORES", "1.0")),
        memory_mb=int(os.getenv("HACKER_RUNNER_MEMORY_MB", "1024")),
        timeout_seconds=int(os.getenv("HACKER_RUNNER_TIMEOUT_SECONDS", "300")),
    )
