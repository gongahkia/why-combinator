from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import RunState
from app.db.models import Challenge, Run
from app.scheduler.checkpoints import (
    AdaptiveCheckpointInterval,
    enqueue_periodic_checkpoint_scores,
    resolve_adaptive_checkpoint_interval_seconds,
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


class _FakeInspector:
    def __init__(self, *, active: dict[str, list[object]], reserved: dict[str, list[object]]) -> None:
        self._active = active
        self._reserved = reserved

    def active(self) -> dict[str, list[object]]:
        return self._active

    def reserved(self) -> dict[str, list[object]]:
        return self._reserved


def test_resolve_adaptive_checkpoint_interval_scales_with_queue_depth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_adaptive_interval_enabled", lambda: True)
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_adaptive_min_interval_seconds", lambda: 30)
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_adaptive_max_interval_seconds", lambda: 300)
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_adaptive_target_tasks_per_worker", lambda: 4)

    low_depth = resolve_adaptive_checkpoint_interval_seconds(
        120,
        inspect_client=_FakeInspector(active={"worker-a": []}, reserved={"worker-a": []}),
    )
    assert low_depth.interval_seconds == 60
    assert low_depth.queue_depth == 0
    assert low_depth.throughput_capacity == 4

    high_depth = resolve_adaptive_checkpoint_interval_seconds(
        120,
        inspect_client=_FakeInspector(
            active={"worker-a": [object()] * 10},
            reserved={"worker-a": [object()] * 10},
        ),
    )
    assert high_depth.interval_seconds == 300
    assert high_depth.queue_depth == 20
    assert high_depth.throughput_capacity == 4


@pytest.mark.asyncio
async def test_enqueue_periodic_checkpoint_scores_uses_adaptive_interval_decision(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    now = start + timedelta(minutes=4)

    challenge = Challenge(
        title="Adaptive checkpoint interval",
        prompt="Scale checkpoint interval by queue depth and throughput.",
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
    redis_client.store[f"run:{run.id}:next_checkpoint_at"] = (now - timedelta(seconds=1)).isoformat()

    enqueued: list[str] = []
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_interval_seconds", lambda: 60)
    monkeypatch.setattr(
        "app.scheduler.checkpoints.resolve_adaptive_checkpoint_interval_seconds",
        lambda base: AdaptiveCheckpointInterval(interval_seconds=240, queue_depth=20, throughput_capacity=4),
    )
    monkeypatch.setattr("app.scheduler.checkpoints.checkpoint_score.delay", lambda run_id, trace_id: enqueued.append(run_id))

    scheduled = await enqueue_periodic_checkpoint_scores(session, redis_client, now=now)

    assert scheduled == [str(run.id)]
    assert enqueued == [str(run.id)]
    assert redis_client.store[f"run:{run.id}:next_checkpoint_at"] == (now + timedelta(seconds=240)).isoformat()
