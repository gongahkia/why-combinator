from __future__ import annotations

from datetime import UTC, datetime

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
