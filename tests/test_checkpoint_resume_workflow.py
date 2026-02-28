from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import RunState
from app.db.models import Challenge, CheckpointSnapshot, Run
from app.scheduler.checkpoints import enqueue_periodic_checkpoint_scores


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str) -> None:
        self.store[key] = value


@pytest.mark.asyncio
async def test_resume_workflow_enqueues_from_last_completed_checkpoint_after_crash(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    challenge = Challenge(
        title="Resume workflow test",
        prompt="Resume from latest checkpoint after crash.",
        iteration_window_seconds=7200,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, started_at=start, config_snapshot={})
    session.add(run)
    await session.flush()

    session.add(
        CheckpointSnapshot(
            run_id=run.id,
            checkpoint_id="checkpoint:20260228T000500Z",
            captured_at=start + timedelta(minutes=5),
            active_weights={"quality": 1.0},
            active_policies={"risk_appetite": "balanced"},
        )
    )
    await session.commit()

    redis_client = _FakeAsyncRedis()
    enqueued: list[str] = []
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_interval_seconds", lambda: 300)
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_max_enqueues_per_tick", lambda: 10)
    monkeypatch.setattr("app.scheduler.checkpoints.checkpoint_score.delay", lambda run_id, trace_id: enqueued.append(run_id))

    now = start + timedelta(minutes=11)
    scheduled = await enqueue_periodic_checkpoint_scores(session, redis_client, now=now)

    assert scheduled == [str(run.id)]
    assert enqueued == [str(run.id)]
    key = f"run:{run.id}:next_checkpoint_at"
    assert redis_client.store[key] == (now + timedelta(minutes=5)).isoformat()


@pytest.mark.asyncio
async def test_resume_workflow_waits_until_next_interval_after_latest_checkpoint(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    challenge = Challenge(
        title="Resume no-op test",
        prompt="Do not enqueue before next checkpoint interval.",
        iteration_window_seconds=7200,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, started_at=start, config_snapshot={})
    session.add(run)
    await session.flush()

    session.add(
        CheckpointSnapshot(
            run_id=run.id,
            checkpoint_id="checkpoint:20260228T000500Z",
            captured_at=start + timedelta(minutes=5),
            active_weights={"quality": 1.0},
            active_policies={"risk_appetite": "balanced"},
        )
    )
    await session.commit()

    redis_client = _FakeAsyncRedis()
    enqueued: list[str] = []
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_interval_seconds", lambda: 300)
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_max_enqueues_per_tick", lambda: 10)
    monkeypatch.setattr("app.scheduler.checkpoints.checkpoint_score.delay", lambda run_id, trace_id: enqueued.append(run_id))

    now = start + timedelta(minutes=9)
    scheduled = await enqueue_periodic_checkpoint_scores(session, redis_client, now=now)

    assert scheduled == []
    assert enqueued == []
    key = f"run:{run.id}:next_checkpoint_at"
    assert redis_client.store[key] == (start + timedelta(minutes=10)).isoformat()
