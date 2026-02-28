from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import RunState
from app.db.models import Challenge, Run
from app.queue import jobs as queue_jobs
from app.scheduler.heartbeat import (
    SCHEDULER_LEADER_FAILOVER_REQUEST_KEY,
    monitor_scheduler_heartbeat_and_trigger_failover,
    publish_scheduler_leader_heartbeat,
)


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,  # noqa: ARG002
        nx: bool | None = None,
    ) -> bool | None:
        if nx:
            if key in self.store:
                return False
            self.store[key] = value
            return True
        self.store[key] = value
        return None

    async def expire(self, key: str, seconds: int) -> bool:  # noqa: ARG002
        return key in self.store


@pytest.mark.asyncio
async def test_scheduler_heartbeat_monitor_triggers_failover_and_dispatches_due_checkpoints(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    challenge = Challenge(
        title="Heartbeat failover test",
        prompt="Failover should dispatch checkpoints when leader heartbeat is missing.",
        iteration_window_seconds=3600,
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
    enqueued: list[str] = []
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_interval_seconds", lambda: 60)
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_max_enqueues_per_tick", lambda: 10)
    monkeypatch.setattr("app.scheduler.checkpoints.checkpoint_score.delay", lambda run_id, trace_id: enqueued.append(run_id))

    now = start + timedelta(minutes=2)
    result = await monitor_scheduler_heartbeat_and_trigger_failover(session, redis_client, now=now)

    assert result.failover_triggered is True
    assert result.reason == "missing_heartbeat"
    assert result.scheduled_run_ids == [str(run.id)]
    assert enqueued == [str(run.id)]
    assert SCHEDULER_LEADER_FAILOVER_REQUEST_KEY in redis_client.store


@pytest.mark.asyncio
async def test_scheduler_heartbeat_monitor_no_failover_when_heartbeat_is_fresh(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    challenge = Challenge(
        title="Heartbeat healthy test",
        prompt="Healthy heartbeat should suppress failover.",
        iteration_window_seconds=3600,
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
    now = start + timedelta(minutes=2)
    await publish_scheduler_leader_heartbeat(redis_client, leader_id="scheduler-a", now=now - timedelta(seconds=5))
    enqueued: list[str] = []
    monkeypatch.setattr("app.scheduler.checkpoints.checkpoint_score.delay", lambda run_id, trace_id: enqueued.append(run_id))

    result = await monitor_scheduler_heartbeat_and_trigger_failover(session, redis_client, now=now)

    assert result.failover_triggered is False
    assert result.reason == "healthy"
    assert result.scheduled_run_ids == []
    assert enqueued == []


def test_scheduler_heartbeat_monitor_task_delegates_to_orchestrator_job(monkeypatch) -> None:
    monkeypatch.setattr(
        queue_jobs,
        "run_scheduler_heartbeat_monitor_job",
        lambda trace_id: {
            "job_type": "scheduler-heartbeat-monitor",
            "status": "completed",
            "trace_id": trace_id,
            "failover_triggered": "true",
            "reason": "missing_heartbeat",
            "scheduled_runs": "1",
        },
    )

    result = queue_jobs.scheduler_heartbeat_monitor.run("trace-heartbeat")

    assert result["job_type"] == "scheduler-heartbeat-monitor"
    assert result["trace_id"] == "trace-heartbeat"
