from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import RunState
from app.db.models import Challenge, Run
from app.queue import jobs as queue_jobs
from app.scheduler.run_timeout import (
    fail_stale_runs_without_worker_heartbeat,
    run_worker_heartbeat_key,
)


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str) -> None:
        self.store[key] = value


@pytest.mark.asyncio
async def test_watchdog_fails_running_run_with_stale_or_missing_worker_heartbeat(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    challenge = Challenge(
        title="Run heartbeat stale test",
        prompt="Fail stale runs when worker heartbeat is missing.",
        iteration_window_seconds=7200,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, started_at=start, config_snapshot={})
    session.add(run)
    await session.commit()

    redis_client = _FakeAsyncRedis()
    monkeypatch.setattr("app.scheduler.run_timeout.load_run_heartbeat_stale_seconds", lambda: 60)

    failed = await fail_stale_runs_without_worker_heartbeat(session, redis_client, now=start + timedelta(minutes=5))

    assert failed == [str(run.id)]
    await session.refresh(run)
    assert run.state == RunState.FAILED
    assert run.ended_at is not None


@pytest.mark.asyncio
async def test_watchdog_keeps_run_running_when_heartbeat_is_recent(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    challenge = Challenge(
        title="Run heartbeat fresh test",
        prompt="Do not fail runs with recent worker heartbeat.",
        iteration_window_seconds=7200,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, started_at=start, config_snapshot={})
    session.add(run)
    await session.commit()

    now = start + timedelta(minutes=5)
    redis_client = _FakeAsyncRedis()
    await redis_client.set(run_worker_heartbeat_key(run.id), (now - timedelta(seconds=30)).isoformat())
    monkeypatch.setattr("app.scheduler.run_timeout.load_run_heartbeat_stale_seconds", lambda: 60)

    failed = await fail_stale_runs_without_worker_heartbeat(session, redis_client, now=now)

    assert failed == []
    await session.refresh(run)
    assert run.state == RunState.RUNNING


def test_run_heartbeat_watchdog_task_delegates_to_orchestrator_job(monkeypatch) -> None:
    monkeypatch.setattr(
        queue_jobs,
        "run_stale_run_heartbeat_watchdog_job",
        lambda trace_id: {
            "job_type": "run-heartbeat-watchdog",
            "status": "completed",
            "trace_id": trace_id,
            "failed_runs": "2",
        },
    )

    response = queue_jobs.run_heartbeat_watchdog.run("trace-watchdog")

    assert response["job_type"] == "run-heartbeat-watchdog"
    assert response["trace_id"] == "trace-watchdog"
