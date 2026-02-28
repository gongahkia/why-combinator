from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.queue.celery_app import celery_app

router = APIRouter(tags=["infra"])


async def _check_postgres(request: Request) -> dict[str, object]:
    try:
        async with request.app.state.db_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


async def _check_redis(request: Request) -> dict[str, object]:
    try:
        await request.app.state.redis.ping()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_queue_worker_heartbeat() -> dict[str, object]:
    try:
        ping = celery_app.control.inspect(timeout=1.0).ping() or {}
        if not ping:
            return {"status": "error", "detail": "no active celery workers responding to heartbeat ping"}
        return {"status": "ok", "workers": sorted(ping.keys())}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


def _check_sandbox_runner() -> dict[str, object]:
    docker_bin = os.getenv("DOCKER_BIN", "docker")
    resolved = shutil.which(docker_bin)
    if resolved is None:
        return {"status": "error", "detail": f"docker binary not found: {docker_bin}"}
    try:
        completed = subprocess.run(
            [resolved, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}
    if completed.returncode != 0:
        return {"status": "error", "detail": completed.stderr.strip() or "docker info failed"}
    return {"status": "ok", "server_version": completed.stdout.strip() or "unknown"}


def _expected_migration_revision() -> str:
    override = os.getenv("REQUIRED_MIGRATION_REVISION", "").strip()
    if override:
        return override

    versions_dir = Path(__file__).resolve().parents[2] / "migrations" / "versions"
    revisions: list[str] = []
    for migration_file in versions_dir.glob("*.py"):
        try:
            content = migration_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = re.search(r'^revision\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if match:
            revisions.append(match.group(1))
    return sorted(revisions)[-1] if revisions else ""


async def _check_migration_version(request: Request) -> dict[str, object]:
    expected_revision = _expected_migration_revision()
    if not expected_revision:
        return {"status": "error", "detail": "no migration revision found in local repository"}
    try:
        async with request.app.state.db_engine.connect() as connection:
            row = (await connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))).first()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc), "expected_revision": expected_revision}
    if row is None:
        return {"status": "error", "detail": "alembic_version table is empty", "expected_revision": expected_revision}
    current_revision = str(row[0])
    if current_revision != expected_revision:
        return {
            "status": "error",
            "detail": "database migration version does not match expected revision",
            "expected_revision": expected_revision,
            "current_revision": current_revision,
        }
    return {"status": "ok", "expected_revision": expected_revision, "current_revision": current_revision}


def _check_model_provider_credentials() -> dict[str, object]:
    api_key = os.getenv("MODEL_API_KEY", "").strip()
    if not api_key:
        return {"status": "error", "detail": "MODEL_API_KEY is not set"}
    return {"status": "ok"}


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    checks: dict[str, Any] = {
        "postgres": await _check_postgres(request),
        "redis": await _check_redis(request),
        "queue_worker_heartbeat": _check_queue_worker_heartbeat(),
        "sandbox_runner": _check_sandbox_runner(),
    }
    overall_status = "ok" if all(value.get("status") == "ok" for value in checks.values()) else "degraded"
    http_status = 200 if overall_status == "ok" else 503
    return JSONResponse(status_code=http_status, content={"status": overall_status, "checks": checks})


@router.get("/readiness")
async def readiness(request: Request) -> JSONResponse:
    checks: dict[str, Any] = {
        "migration_version": await _check_migration_version(request),
        "model_provider_credentials": _check_model_provider_credentials(),
    }
    overall_status = "ready" if all(value.get("status") == "ok" for value in checks.values()) else "not_ready"
    http_status = 200 if overall_status == "ready" else 503
    return JSONResponse(status_code=http_status, content={"status": overall_status, "checks": checks})
