from __future__ import annotations

from app.queue import jobs as queue_jobs
from app.queue.checkpoint_backfill import list_failed_checkpoint_backfills


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
        self._kv: dict[str, str] = {}
        self._lock = lock or _FakeLock()

    def hset(self, key: str, field: str, value: str) -> None:
        self._hashes.setdefault(key, {})[field] = value

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))

    def hdel(self, key: str, field: str) -> None:
        self._hashes.setdefault(key, {}).pop(field, None)

    def lock(self, name: str, timeout: int, blocking: bool = False) -> _FakeLock:  # noqa: ARG002
        return self._lock

    def get(self, key: str) -> str | None:
        return self._kv.get(key)

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        return None


def test_checkpoint_scoring_chaos_recovery_requeues_once_and_clears_backfill(monkeypatch) -> None:
    fake_redis = _FakeRedis()
    monkeypatch.setattr(queue_jobs, "_with_budget_guard", lambda run_id, task_name, default_cost: (True, {}))  # noqa: ARG005
    monkeypatch.setattr(queue_jobs, "create_redis_client", lambda: fake_redis)
    monkeypatch.setattr(queue_jobs, "_record_run_worker_heartbeat", lambda run_id: None)

    run_job_calls = {"count": 0}

    def _flaky_checkpoint_score_job(run_id: str, trace_id: str | None = None) -> dict[str, str]:
        run_job_calls["count"] += 1
        if run_job_calls["count"] == 1:
            raise RuntimeError("database connection refused")
        return {
            "job_type": "checkpoint-score",
            "run_id": run_id,
            "status": "completed",
            "trace_id": trace_id or "",
            "checkpoint_id": "checkpoint:chaos",
            "scored_submissions": "1",
            "skipped_submissions": "0",
            "judge_scores_created": "0",
            "leaderboard_entries": "1",
        }

    monkeypatch.setattr(queue_jobs, "run_checkpoint_score_job", _flaky_checkpoint_score_job)
    scheduled_backfill_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        queue_jobs.backfill_failed_checkpoints,
        "apply_async",
        lambda **kwargs: scheduled_backfill_calls.append(kwargs),
    )

    first = queue_jobs.checkpoint_score.run("run-chaos", "trace-chaos")
    assert first["status"] == "dependency_failed_backfill_queued"
    assert len(list_failed_checkpoint_backfills(fake_redis)) == 1
    assert len(scheduled_backfill_calls) == 1

    monkeypatch.setattr(queue_jobs, "_dependencies_recovered_for_checkpoint_backfill", lambda: True)
    monkeypatch.setattr(queue_jobs, "load_checkpoint_backfill_max_enqueues", lambda: 10)
    replayed_results: list[dict[str, str]] = []
    monkeypatch.setattr(
        queue_jobs.checkpoint_score,
        "delay",
        lambda run_id, trace_id: replayed_results.append(queue_jobs.checkpoint_score.run(run_id, trace_id)),
    )

    recovered = queue_jobs.backfill_failed_checkpoints.run("trace-chaos-recover")

    assert recovered["status"] == "completed"
    assert recovered["enqueued"] == "1"
    assert recovered["remaining"] == "0"
    assert len(replayed_results) == 1
    assert replayed_results[0]["status"] == "completed"
    assert run_job_calls["count"] == 2
    assert list_failed_checkpoint_backfills(fake_redis) == []
