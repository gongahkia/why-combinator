from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import redis

IN_FLIGHT_TASKS_KEY = "queue:in_flight_tasks"
RECOVERABLE_TASKS_KEY = "queue:recoverable_tasks"


def load_worker_drain_timeout_seconds() -> int:
    return int(os.getenv("WORKER_DRAIN_TIMEOUT_SECONDS", "15"))


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def track_in_flight_task(
    redis_client: redis.Redis,
    *,
    task_id: str,
    task_name: str,
    args: list[Any],
    kwargs: dict[str, Any],
    worker_pid: int,
    worker_hostname: str | None,
) -> None:
    payload = {
        "task_id": task_id,
        "task_name": task_name,
        "args": args,
        "kwargs": kwargs,
        "worker_pid": worker_pid,
        "worker_hostname": worker_hostname or "",
        "started_at": datetime.now(UTC).isoformat(),
    }
    redis_client.hset(IN_FLIGHT_TASKS_KEY, task_id, _json_dumps(payload))


def clear_in_flight_task(redis_client: redis.Redis, task_id: str) -> None:
    redis_client.hdel(IN_FLIGHT_TASKS_KEY, task_id)


def list_in_flight_tasks(redis_client: redis.Redis) -> list[dict[str, Any]]:
    raw_entries = redis_client.hgetall(IN_FLIGHT_TASKS_KEY)
    parsed: list[dict[str, Any]] = []
    for payload in raw_entries.values():
        row = _json_loads(payload)
        if row is not None:
            parsed.append(row)
    return parsed


def mark_recoverable_task(
    redis_client: redis.Redis,
    *,
    task_payload: dict[str, Any],
    reason: str,
) -> bool:
    task_id = str(task_payload.get("task_id", "")).strip()
    if not task_id:
        return False
    recoverable_payload = {
        **task_payload,
        "recoverable_reason": reason,
        "recoverable_at": datetime.now(UTC).isoformat(),
    }
    claimed = redis_client.hsetnx(RECOVERABLE_TASKS_KEY, task_id, _json_dumps(recoverable_payload))
    clear_in_flight_task(redis_client, task_id)
    return bool(claimed)


def list_recoverable_tasks(redis_client: redis.Redis) -> list[dict[str, Any]]:
    raw_entries = redis_client.hgetall(RECOVERABLE_TASKS_KEY)
    parsed: list[dict[str, Any]] = []
    for payload in raw_entries.values():
        row = _json_loads(payload)
        if row is not None:
            parsed.append(row)
    return parsed


def remove_recoverable_task(redis_client: redis.Redis, task_id: str) -> None:
    redis_client.hdel(RECOVERABLE_TASKS_KEY, task_id)
