from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class SandboxCleanupSummary:
    deleted_workdirs: int
    deleted_volumes: int
    scanned_workdirs: int
    scanned_volumes: int
    errors: list[str]

    def as_dict(self) -> dict[str, str]:
        return {
            "deleted_workdirs": str(self.deleted_workdirs),
            "deleted_volumes": str(self.deleted_volumes),
            "scanned_workdirs": str(self.scanned_workdirs),
            "scanned_volumes": str(self.scanned_volumes),
            "errors": json.dumps(self.errors),
        }


def load_sandbox_workdir_root() -> Path:
    configured = os.getenv("SANDBOX_WORKDIR_ROOT", tempfile.gettempdir())
    return Path(configured)


def load_sandbox_workdir_ttl_seconds() -> int:
    return int(os.getenv("SANDBOX_WORKDIR_TTL_SECONDS", str(6 * 60 * 60)))


def load_sandbox_volume_prefix() -> str:
    return os.getenv("SANDBOX_VOLUME_PREFIX", "hackathon-sandbox-").strip() or "hackathon-sandbox-"


def load_sandbox_volume_ttl_seconds() -> int:
    return int(os.getenv("SANDBOX_VOLUME_TTL_SECONDS", str(24 * 60 * 60)))


def load_sandbox_cleanup_docker_bin() -> str:
    return os.getenv("DOCKER_BIN", "docker")


def _is_expired(timestamp: datetime, now: datetime, ttl_seconds: int) -> bool:
    return (now - timestamp) >= timedelta(seconds=max(1, ttl_seconds))


def cleanup_expired_sandbox_workdirs(
    *,
    now: datetime | None = None,
    root: Path | None = None,
    ttl_seconds: int | None = None,
) -> tuple[int, int, list[str]]:
    current_time = now or datetime.now(UTC)
    workdir_root = root or load_sandbox_workdir_root()
    ttl = ttl_seconds if ttl_seconds is not None else load_sandbox_workdir_ttl_seconds()

    deleted = 0
    scanned = 0
    errors: list[str] = []

    if not workdir_root.exists():
        return deleted, scanned, errors

    for path in workdir_root.glob("hacker-agent-*"):
        if not path.is_dir():
            continue
        scanned += 1
        try:
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        except OSError as exc:
            errors.append(f"workdir_stat_failed:{path}:{exc}")
            continue
        if not _is_expired(modified_at, current_time, ttl):
            continue
        try:
            shutil.rmtree(path, ignore_errors=False)
            deleted += 1
        except OSError as exc:
            errors.append(f"workdir_delete_failed:{path}:{exc}")

    return deleted, scanned, errors


def _parse_timestamp(raw: str) -> datetime | None:
    normalized = raw.strip()
    if normalized.endswith(" UTC"):
        normalized = normalized.removesuffix(" UTC")
    candidates = (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
    )
    for pattern in candidates:
        try:
            parsed = datetime.strptime(normalized, pattern)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            continue
    return None


def _docker_volume_names(docker_bin: str) -> list[str]:
    completed = subprocess.run(
        [docker_bin, "volume", "ls", "--format", "{{.Name}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _docker_volume_created_at(docker_bin: str, volume_name: str) -> datetime | None:
    completed = subprocess.run(
        [docker_bin, "volume", "inspect", volume_name, "--format", "{{.CreatedAt}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return _parse_timestamp(completed.stdout)


def cleanup_expired_sandbox_volumes(
    *,
    now: datetime | None = None,
    docker_bin: str | None = None,
    volume_prefix: str | None = None,
    ttl_seconds: int | None = None,
) -> tuple[int, int, list[str]]:
    current_time = now or datetime.now(UTC)
    active_docker_bin = docker_bin or load_sandbox_cleanup_docker_bin()
    prefix = volume_prefix if volume_prefix is not None else load_sandbox_volume_prefix()
    ttl = ttl_seconds if ttl_seconds is not None else load_sandbox_volume_ttl_seconds()

    deleted = 0
    scanned = 0
    errors: list[str] = []

    try:
        volume_names = _docker_volume_names(active_docker_bin)
    except OSError as exc:
        return deleted, scanned, [f"docker_volume_ls_failed:{exc}"]

    for volume_name in volume_names:
        if prefix and not volume_name.startswith(prefix):
            continue
        scanned += 1
        try:
            created_at = _docker_volume_created_at(active_docker_bin, volume_name)
        except OSError as exc:
            errors.append(f"docker_volume_inspect_failed:{volume_name}:{exc}")
            continue
        if created_at is None:
            errors.append(f"docker_volume_inspect_failed:{volume_name}:missing_created_at")
            continue
        if not _is_expired(created_at, current_time, ttl):
            continue

        try:
            removed = subprocess.run(
                [active_docker_bin, "volume", "rm", volume_name],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            errors.append(f"docker_volume_delete_failed:{volume_name}:{exc}")
            continue
        if removed.returncode != 0:
            stderr = (removed.stderr or "").strip()
            errors.append(f"docker_volume_delete_failed:{volume_name}:{stderr}")
            continue
        deleted += 1

    return deleted, scanned, errors


def cleanup_sandbox_resources(now: datetime | None = None) -> SandboxCleanupSummary:
    current_time = now or datetime.now(UTC)
    deleted_workdirs, scanned_workdirs, workdir_errors = cleanup_expired_sandbox_workdirs(now=current_time)
    deleted_volumes, scanned_volumes, volume_errors = cleanup_expired_sandbox_volumes(now=current_time)
    return SandboxCleanupSummary(
        deleted_workdirs=deleted_workdirs,
        deleted_volumes=deleted_volumes,
        scanned_workdirs=scanned_workdirs,
        scanned_volumes=scanned_volumes,
        errors=[*workdir_errors, *volume_errors],
    )
