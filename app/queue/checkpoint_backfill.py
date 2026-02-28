from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import redis


CHECKPOINT_BACKFILL_KEY = "queue:checkpoint_backfill"


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _json_loads(raw_value: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def record_failed_checkpoint_backfill(
    redis_client: redis.Redis,
    *,
    run_id: str,
    trace_id: str,
    reason: str,
) -> None:
    payload = {
        "run_id": run_id,
        "trace_id": trace_id,
        "reason": reason,
        "failed_at": datetime.now(UTC).isoformat(),
    }
    redis_client.hset(CHECKPOINT_BACKFILL_KEY, run_id, _json_dumps(payload))


def list_failed_checkpoint_backfills(redis_client: redis.Redis) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw_value in redis_client.hgetall(CHECKPOINT_BACKFILL_KEY).values():
        if isinstance(raw_value, bytes):
            raw_text = raw_value.decode("utf-8", errors="ignore")
        else:
            raw_text = str(raw_value)
        payload = _json_loads(raw_text)
        if payload is not None:
            rows.append(payload)
    return rows


def clear_failed_checkpoint_backfill(redis_client: redis.Redis, run_id: str) -> None:
    redis_client.hdel(CHECKPOINT_BACKFILL_KEY, run_id)
