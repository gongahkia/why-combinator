from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from app.orchestrator.jobs import reserve_subagent_spawn_quota
from app.orchestrator.subagent_quota import subagent_quota_key


class _ConcurrentQuotaRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self._lock = Lock()

    def eval(self, script: str, num_keys: int, key: str, increment: int, limit: int) -> int:  # noqa: ARG002
        with self._lock:
            used = int(self.store.get(key, "0"))
            if used + int(increment) > int(limit):
                return -1
            used += int(increment)
            self.store[key] = str(used)
            return used

    def get(self, key: str) -> str | None:
        with self._lock:
            return self.store.get(key)

    def close(self) -> None:
        return None


def test_subagent_spawn_budget_ledger_consistent_under_concurrent_attempts(monkeypatch) -> None:
    redis_client = _ConcurrentQuotaRedis()
    monkeypatch.setenv("SUBAGENT_SPAWN_QUOTA_PER_AGENT", "5")
    monkeypatch.setattr("app.orchestrator.jobs.create_redis_client", lambda: redis_client)

    run_id = "run-budget-ledger"
    parent_agent_id = "agent-root"
    attempts = 20

    with ThreadPoolExecutor(max_workers=attempts) as executor:
        results = list(executor.map(lambda _: reserve_subagent_spawn_quota(run_id, parent_agent_id), range(attempts)))

    accepted = [result for result in results if result["status"] == "accepted"]
    exhausted = [result for result in results if result["status"] == "quota_exhausted"]

    assert len(accepted) == 5
    assert len(exhausted) == attempts - 5
    assert int(redis_client.get(subagent_quota_key(run_id, parent_agent_id)) or "0") == 5
    assert all(int(result["spawn_quota_remaining"]) >= 0 for result in results)
