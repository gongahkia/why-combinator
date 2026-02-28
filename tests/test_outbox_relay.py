from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.challenges import ChallengeCreateRequest, create_challenge
from app.api.runs import start_run
from app.db.models import OutboxEvent
from app.events.bus import make_run_lifecycle_event
from app.events.outbox import enqueue_run_lifecycle_event_outbox, relay_outbox_events
from app.queue import jobs as queue_jobs


class _FakeRelayRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []
        self.dedup_keys: set[str] = set()

    def eval(self, script: str, num_keys: int, dedup_key: str, ttl_ms: int, stream_name: str, payload_json: str) -> int:  # noqa: ARG002
        if dedup_key in self.dedup_keys:
            return 0
        self.dedup_keys.add(dedup_key)
        self.published.append((stream_name, payload_json))
        return 1


class _FlakyRelayRedis(_FakeRelayRedis):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def eval(self, script: str, num_keys: int, dedup_key: str, ttl_ms: int, stream_name: str, payload_json: str) -> int:  # noqa: ARG002
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary redis outage")
        return super().eval(script, num_keys, dedup_key, ttl_ms, stream_name, payload_json)


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.kv: dict[str, int] = {}

    async def setnx(self, key: str, value: int) -> bool:
        if key in self.kv:
            return False
        self.kv[key] = value
        return True


@pytest.mark.asyncio
async def test_outbox_relay_publishes_pending_events_once(session: AsyncSession) -> None:
    event = make_run_lifecycle_event(
        event_type="run_started",
        run_id=uuid.uuid4(),
        challenge_id=uuid.uuid4(),
        payload={"started_at": datetime.now(UTC).isoformat()},
    )
    await enqueue_run_lifecycle_event_outbox(session, event)
    await session.commit()

    relay_redis = _FakeRelayRedis()
    result = await relay_outbox_events(session, relay_redis, batch_size=10)
    await session.commit()

    assert result.processed == 1
    assert result.published == 1
    assert result.deduplicated == 0
    assert result.failed == 0
    assert len(relay_redis.published) == 1

    second = await relay_outbox_events(session, relay_redis, batch_size=10)
    assert second.processed == 0
    assert second.published == 0


@pytest.mark.asyncio
async def test_outbox_relay_marks_deduplicated_event_as_published(session: AsyncSession) -> None:
    event = make_run_lifecycle_event(
        event_type="run_started",
        run_id=uuid.uuid4(),
        challenge_id=uuid.uuid4(),
        payload={"started_at": datetime.now(UTC).isoformat()},
    )
    outbox_row = await enqueue_run_lifecycle_event_outbox(session, event)
    await session.commit()

    relay_redis = _FakeRelayRedis()
    relay_redis.dedup_keys.add(f"eventbus:published:{outbox_row.id}")

    result = await relay_outbox_events(session, relay_redis, batch_size=10)
    await session.commit()

    assert result.processed == 1
    assert result.published == 0
    assert result.deduplicated == 1
    persisted = await session.get(OutboxEvent, outbox_row.id)
    assert persisted is not None
    assert persisted.published_at is not None
    assert persisted.publish_attempts == 1


@pytest.mark.asyncio
async def test_outbox_relay_retry_publishes_event_once_without_duplicates(session: AsyncSession) -> None:
    event = make_run_lifecycle_event(
        event_type="run_started",
        run_id=uuid.uuid4(),
        challenge_id=uuid.uuid4(),
        payload={"started_at": datetime.now(UTC).isoformat()},
    )
    outbox_row = await enqueue_run_lifecycle_event_outbox(session, event)
    await session.commit()

    relay_redis = _FlakyRelayRedis()

    first = await relay_outbox_events(session, relay_redis, batch_size=10)
    await session.commit()
    assert first.processed == 1
    assert first.published == 0
    assert first.failed == 1
    persisted_after_failure = await session.get(OutboxEvent, outbox_row.id)
    assert persisted_after_failure is not None
    assert persisted_after_failure.published_at is None
    assert persisted_after_failure.publish_attempts == 1
    assert persisted_after_failure.last_error is not None

    second = await relay_outbox_events(session, relay_redis, batch_size=10)
    await session.commit()
    assert second.processed == 1
    assert second.published == 1
    assert second.failed == 0
    persisted_after_retry = await session.get(OutboxEvent, outbox_row.id)
    assert persisted_after_retry is not None
    assert persisted_after_retry.published_at is not None
    assert persisted_after_retry.publish_attempts == 2
    assert persisted_after_retry.last_error is None
    assert len(relay_redis.published) == 1

    third = await relay_outbox_events(session, relay_redis, batch_size=10)
    assert third.processed == 0
    assert third.published == 0


@pytest.mark.asyncio
async def test_start_run_writes_run_started_event_to_outbox(session: AsyncSession) -> None:
    challenge = await create_challenge(
        ChallengeCreateRequest(
            title="Outbox run start test",
            prompt="Build MVP with outbox event publication.",
            iteration_window_seconds=1800,
            minimum_quality_threshold=0.3,
            risk_appetite="balanced",
            complexity_slider=0.5,
        ),
        _rate_limit=None,
        session=session,
    )

    fake_request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                redis=_FakeAsyncRedis(),
                settings=SimpleNamespace(default_run_budget_units=100, artifact_storage_path="/tmp/artifacts"),
            )
        )
    )

    run = await start_run(challenge.id, request=fake_request, _rate_limit=None, session=session)

    outbox_stmt: Select[tuple[OutboxEvent]] = select(OutboxEvent).where(OutboxEvent.stream_name == "run_events")
    outbox_rows = (await session.execute(outbox_stmt)).scalars().all()

    assert len(outbox_rows) == 1
    assert outbox_rows[0].event_key == f"run:{run.id}:run_started"
    assert outbox_rows[0].published_at is None


def test_queue_relay_outbox_task_delegates_to_orchestrator_job(monkeypatch) -> None:
    monkeypatch.setattr(
        queue_jobs,
        "run_outbox_relay_job",
        lambda trace_id: {
            "job_type": "outbox-relay",
            "status": "completed",
            "trace_id": trace_id,
            "processed": "1",
            "published": "1",
            "deduplicated": "0",
            "failed": "0",
        },
    )

    response = queue_jobs.relay_outbox_events.run("trace-outbox")

    assert response["job_type"] == "outbox-relay"
    assert response["trace_id"] == "trace-outbox"
