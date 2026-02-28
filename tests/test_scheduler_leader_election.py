from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import RunState
from app.db.models import Challenge, Run
from app.scheduler.checkpoints import enqueue_periodic_checkpoint_scores
from app.scheduler.leader_election import try_acquire_or_renew_scheduler_leader


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

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

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def expire(self, key: str, seconds: int) -> bool:  # noqa: ARG002
        return key in self.store


@pytest.mark.asyncio
async def test_scheduler_leader_election_acquires_and_renews_lock() -> None:
    redis_client = _FakeAsyncRedis()

    first = await try_acquire_or_renew_scheduler_leader(redis_client, "leader-a")
    second = await try_acquire_or_renew_scheduler_leader(redis_client, "leader-a")
    third = await try_acquire_or_renew_scheduler_leader(redis_client, "leader-b")

    assert first.is_leader is True
    assert first.acquired_now is True
    assert second.is_leader is True
    assert second.acquired_now is False
    assert third.is_leader is False
    assert third.lock_holder == "leader-a"


@pytest.mark.asyncio
async def test_checkpoint_dispatch_skips_when_scheduler_is_not_current_leader(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenge = Challenge(
        title="Leader lock gating test",
        prompt="Only current lock holder should dispatch checkpoints.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(
        challenge_id=challenge.id,
        state=RunState.RUNNING,
        started_at=datetime(2026, 2, 28, 0, 0, tzinfo=UTC),
        config_snapshot={},
    )
    session.add(run)
    await session.commit()

    redis_client = _FakeAsyncRedis()
    redis_client.store["scheduler:leader:lock"] = "other-leader"
    enqueued: list[str] = []
    monkeypatch.setattr("app.scheduler.checkpoints.load_scheduler_leader_id", lambda: "local-leader")
    monkeypatch.setattr("app.scheduler.checkpoints.checkpoint_score.delay", lambda run_id, trace_id: enqueued.append(run_id))

    scheduled = await enqueue_periodic_checkpoint_scores(
        session,
        redis_client,
        now=datetime(2026, 2, 28, 0, 5, tzinfo=UTC),
    )

    assert scheduled == []
    assert enqueued == []


@pytest.mark.asyncio
async def test_scheduler_failover_maintains_single_active_dispatcher(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenge = Challenge(
        title="Scheduler failover single dispatcher",
        prompt="Only one scheduler instance should dispatch checkpoints at a time.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(
        challenge_id=challenge.id,
        state=RunState.RUNNING,
        started_at=datetime(2026, 2, 28, 0, 0, tzinfo=UTC),
        config_snapshot={},
    )
    session.add(run)
    await session.commit()

    redis_client = _FakeAsyncRedis()
    enqueued: list[tuple[str, datetime]] = []
    leader_id = {"value": "leader-a"}

    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_interval_seconds", lambda: 60)
    monkeypatch.setattr("app.scheduler.checkpoints.load_checkpoint_max_enqueues_per_tick", lambda: 10)
    monkeypatch.setattr("app.scheduler.checkpoints.load_scheduler_leader_id", lambda: leader_id["value"])
    monkeypatch.setattr(
        "app.scheduler.checkpoints.checkpoint_score.delay",
        lambda run_id, trace_id: enqueued.append((run_id, current_time["value"])),
    )

    current_time = {"value": datetime(2026, 2, 28, 0, 5, tzinfo=UTC)}
    redis_client.store[f"run:{run.id}:next_checkpoint_at"] = (current_time["value"] - timedelta(seconds=1)).isoformat()

    scheduled_a = await enqueue_periodic_checkpoint_scores(session, redis_client, now=current_time["value"])
    assert scheduled_a == [str(run.id)]

    leader_id["value"] = "leader-b"
    scheduled_b = await enqueue_periodic_checkpoint_scores(session, redis_client, now=current_time["value"])
    assert scheduled_b == []
    assert [item[0] for item in enqueued] == [str(run.id)]

    # Simulate leader lock expiration and verify only the failover scheduler resumes dispatching.
    redis_client.store.pop("scheduler:leader:lock", None)
    current_time["value"] = datetime(2026, 2, 28, 0, 7, tzinfo=UTC)
    redis_client.store[f"run:{run.id}:next_checkpoint_at"] = (current_time["value"] - timedelta(seconds=1)).isoformat()

    scheduled_after_failover = await enqueue_periodic_checkpoint_scores(session, redis_client, now=current_time["value"])
    assert scheduled_after_failover == [str(run.id)]
    assert [item[0] for item in enqueued] == [str(run.id), str(run.id)]
    assert redis_client.store["scheduler:leader:lock"] == "leader-b"
