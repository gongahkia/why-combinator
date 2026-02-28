from __future__ import annotations

from app.queue import jobs as queue_jobs
from app.queue.checkpoint_backfill import (
    list_failed_checkpoint_backfills,
    record_failed_checkpoint_backfill,
)


class _FakeLock:
    def __init__(self, acquired: bool = True) -> None:
        self._acquired = acquired
        self.released = False

    def acquire(self, blocking: bool = False) -> bool:  # noqa: ARG002
        return self._acquired

    def release(self) -> None:
        self.released = True


class _FakeRedis:
    def __init__(self, lock: _FakeLock | None = None) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._lock = lock or _FakeLock()

    def hset(self, key: str, field: str, value: str) -> None:
        self._hashes.setdefault(key, {})[field] = value

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))

    def hdel(self, key: str, field: str) -> None:
        self._hashes.setdefault(key, {}).pop(field, None)

    def lock(self, name: str, timeout: int, blocking: bool = False) -> _FakeLock:  # noqa: ARG002
        return self._lock

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        return None


def test_checkpoint_score_queues_dependency_failure_for_backfill(monkeypatch) -> None:
    fake_redis = _FakeRedis()

    monkeypatch.setattr(queue_jobs, "_with_budget_guard", lambda run_id, task_name, default_cost: (True, {}))  # noqa: ARG005
    monkeypatch.setattr(queue_jobs, "create_redis_client", lambda: fake_redis)
    monkeypatch.setattr(queue_jobs, "_record_run_worker_heartbeat", lambda run_id: None)

    def _raise_dependency_failure(run_id: str, trace_id: str | None = None) -> dict[str, str]:  # noqa: ARG001
        raise RuntimeError("database connection refused")

    monkeypatch.setattr(queue_jobs, "run_checkpoint_score_job", _raise_dependency_failure)
    scheduled: list[dict[str, object]] = []
    monkeypatch.setattr(
        queue_jobs.backfill_failed_checkpoints,
        "apply_async",
        lambda **kwargs: scheduled.append(kwargs),
    )

    result = queue_jobs.checkpoint_score.run("run-backfill-1", "trace-1")

    assert result["status"] == "dependency_failed_backfill_queued"
    assert result["run_id"] == "run-backfill-1"
    pending_backfills = list_failed_checkpoint_backfills(fake_redis)
    assert len(pending_backfills) == 1
    assert pending_backfills[0]["run_id"] == "run-backfill-1"
    assert scheduled


def test_backfill_failed_checkpoints_requeues_pending_runs_when_dependencies_recover(monkeypatch) -> None:
    fake_redis = _FakeRedis()
    record_failed_checkpoint_backfill(
        fake_redis,
        run_id="run-backfill-2",
        trace_id="trace-2",
        reason="redis connection reset",
    )

    monkeypatch.setattr(queue_jobs, "create_redis_client", lambda: fake_redis)
    monkeypatch.setattr(queue_jobs, "_dependencies_recovered_for_checkpoint_backfill", lambda: True)
    monkeypatch.setattr(queue_jobs, "load_checkpoint_backfill_max_enqueues", lambda: 10)
    enqueued: list[tuple[str, str]] = []
    monkeypatch.setattr(
        queue_jobs.checkpoint_score,
        "delay",
        lambda run_id, trace_id: enqueued.append((run_id, trace_id)),
    )

    result = queue_jobs.backfill_failed_checkpoints.run("trace-backfill")

    assert result["status"] == "completed"
    assert result["enqueued"] == "1"
    assert result["remaining"] == "0"
    assert len(enqueued) == 1
    assert enqueued[0][0] == "run-backfill-2"
    assert list_failed_checkpoint_backfills(fake_redis) == []


def test_backfill_failed_checkpoints_defers_when_dependencies_remain_unhealthy(monkeypatch) -> None:
    fake_redis = _FakeRedis()
    record_failed_checkpoint_backfill(
        fake_redis,
        run_id="run-backfill-3",
        trace_id="trace-3",
        reason="postgres temporarily unavailable",
    )

    monkeypatch.setattr(queue_jobs, "create_redis_client", lambda: fake_redis)
    monkeypatch.setattr(queue_jobs, "_dependencies_recovered_for_checkpoint_backfill", lambda: False)
    scheduled: list[dict[str, object]] = []
    monkeypatch.setattr(
        queue_jobs.backfill_failed_checkpoints,
        "apply_async",
        lambda **kwargs: scheduled.append(kwargs),
    )

    result = queue_jobs.backfill_failed_checkpoints.run("trace-backfill-unhealthy")

    assert result["status"] == "dependencies_unhealthy"
    assert result["enqueued"] == "0"
    assert result["remaining"] == "1"
    assert len(list_failed_checkpoint_backfills(fake_redis)) == 1
    assert scheduled
