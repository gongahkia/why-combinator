from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.queue import jobs as queue_jobs
from app.sandbox.cleanup import cleanup_expired_sandbox_volumes, cleanup_expired_sandbox_workdirs


def test_cleanup_expired_sandbox_workdirs_removes_only_stale_paths(tmp_path: Path) -> None:
    now = datetime(2026, 2, 28, 0, 10, tzinfo=UTC)
    stale_dir = tmp_path / "hacker-agent-stale"
    fresh_dir = tmp_path / "hacker-agent-fresh"
    other_dir = tmp_path / "not-a-sandbox-workdir"
    stale_dir.mkdir()
    fresh_dir.mkdir()
    other_dir.mkdir()

    stale_time = (now - timedelta(hours=8)).timestamp()
    fresh_time = (now - timedelta(minutes=10)).timestamp()
    os.utime(stale_dir, (stale_time, stale_time))
    os.utime(fresh_dir, (fresh_time, fresh_time))

    deleted, scanned, errors = cleanup_expired_sandbox_workdirs(
        now=now,
        root=tmp_path,
        ttl_seconds=60 * 60,
    )

    assert deleted == 1
    assert scanned == 2
    assert errors == []
    assert not stale_dir.exists()
    assert fresh_dir.exists()
    assert other_dir.exists()


def test_cleanup_expired_sandbox_volumes_deletes_only_stale_prefixed_volumes(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 2, 28, 0, 10, tzinfo=UTC)
    calls: list[list[str]] = []

    def _fake_run(cmd, capture_output, text, check):  # noqa: ANN001, ANN202, ARG001
        calls.append(cmd)
        if cmd[:4] == ["docker", "volume", "ls", "--format"]:
            return SimpleNamespace(returncode=0, stdout="hackathon-sandbox-old\nhackathon-sandbox-new\nother-volume\n", stderr="")
        if cmd[:4] == ["docker", "volume", "inspect", "hackathon-sandbox-old"]:
            return SimpleNamespace(returncode=0, stdout="2026-02-27T00:00:00Z\n", stderr="")
        if cmd[:4] == ["docker", "volume", "inspect", "hackathon-sandbox-new"]:
            return SimpleNamespace(returncode=0, stdout="2026-02-28T00:05:00Z\n", stderr="")
        if cmd[:3] == ["docker", "volume", "rm"] and cmd[3] == "hackathon-sandbox-old":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="unsupported")

    monkeypatch.setattr("app.sandbox.cleanup.subprocess.run", _fake_run)

    deleted, scanned, errors = cleanup_expired_sandbox_volumes(
        now=now,
        docker_bin="docker",
        volume_prefix="hackathon-sandbox-",
        ttl_seconds=60 * 60,
    )

    assert deleted == 1
    assert scanned == 2
    assert errors == []
    assert ["docker", "volume", "rm", "hackathon-sandbox-old"] in calls


def test_cleanup_sandbox_resources_task_returns_orchestrator_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        queue_jobs,
        "run_sandbox_cleanup_job",
        lambda trace_id=None: {
            "job_type": "sandbox-cleanup",
            "status": "completed",
            "trace_id": trace_id or "",
            "deleted_workdirs": "3",
            "deleted_volumes": "2",
            "scanned_workdirs": "5",
            "scanned_volumes": "4",
            "errors": "[]",
        },
    )

    result = queue_jobs.cleanup_sandbox_resources.run("trace-cleanup")

    assert result["job_type"] == "sandbox-cleanup"
    assert result["status"] == "completed"
    assert result["trace_id"] == "trace-cleanup"
    assert result["deleted_workdirs"] == "3"
    assert result["deleted_volumes"] == "2"
