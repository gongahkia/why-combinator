from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import RunState
from app.db.models import Challenge, Run
from app.scheduler.checkpoints import enqueue_periodic_checkpoint_scores, _run_checkpoint_jitter_seconds


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
async def test_checkpoint_scheduler_applies_deterministic_per_run_jitter(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    now = start + timedelta(minutes=8)

    challenge = Challenge(
        title="Checkpoint jitter control",
        prompt="Stagger checkpoint schedules to avoid queue spikes.",
        iteration_window_seconds=7200,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run_a = Run(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        challenge_id=challenge.id,
        state=RunState.RUNNING,
        started_at=start,
        config_snapshot={},
    )
    run_b = Run(
        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        challenge_id=challenge.id,
        state=RunState.RUNNING,
        started_at=start,
        config_snapshot={},
    )
    session.add_all([run_a, run_b])
    await session.commit()

    redis_client = _FakeAsyncRedis()
    redis_client.store[f"run:{run_a.id}:next_checkpoint_at"] = (now - timedelta(seconds=5)).isoformat()
    redis_client.store[f"run:{run_b.id}:next_checkpoint_at"] = (now - timedelta(seconds=5)).isoformat()

    enqueued: list[str] = []
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_interval_seconds", lambda: 300)
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_jitter_seconds", lambda: 90)
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_max_enqueues_per_tick", lambda: 10)
    monkeypatch.setattr("app.scheduler.checkpoints.checkpoint_score.delay", lambda run_id, trace_id: enqueued.append(run_id))

    scheduled = await enqueue_periodic_checkpoint_scores(session, redis_client, now=now)

    assert set(scheduled) == {str(run_a.id), str(run_b.id)}
    assert set(enqueued) == {str(run_a.id), str(run_b.id)}

    base_next_checkpoint = now + timedelta(seconds=300)
    run_a_next = datetime.fromisoformat(redis_client.store[f"run:{run_a.id}:next_checkpoint_at"])
    run_b_next = datetime.fromisoformat(redis_client.store[f"run:{run_b.id}:next_checkpoint_at"])

    run_a_offset = int((run_a_next - base_next_checkpoint).total_seconds())
    run_b_offset = int((run_b_next - base_next_checkpoint).total_seconds())

    assert run_a_offset == _run_checkpoint_jitter_seconds(run_a.id, interval_seconds=300, jitter_window_seconds=90)
    assert run_b_offset == _run_checkpoint_jitter_seconds(run_b.id, interval_seconds=300, jitter_window_seconds=90)
    assert 0 <= run_a_offset <= 90
    assert 0 <= run_b_offset <= 90
