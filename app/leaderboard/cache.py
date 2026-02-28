from __future__ import annotations

import json
import os
import uuid
from typing import Any

from app.queue.budget import create_redis_client


def load_leaderboard_cache_ttl_seconds() -> int:
    return int(os.getenv("LEADERBOARD_CACHE_TTL_SECONDS", "300"))


def load_leaderboard_cursor_snapshot_ttl_seconds() -> int:
    return int(os.getenv("LEADERBOARD_CURSOR_SNAPSHOT_TTL_SECONDS", "300"))


def leaderboard_scoreboard_cache_key(run_id: uuid.UUID) -> str:
    return f"leaderboard:run:{run_id}:scoreboard"


def leaderboard_cursor_snapshot_cache_key(run_id: uuid.UUID, snapshot_id: str) -> str:
    return f"leaderboard:run:{run_id}:snapshot:{snapshot_id}"


def _parse_cached_row_list(raw_payload: str) -> list[dict[str, Any]] | None:
    payload = json.loads(raw_payload)
    if not isinstance(payload, list):
        return None
    parsed: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            parsed.append(item)
    return parsed


def read_leaderboard_scoreboard_cache(run_id: uuid.UUID) -> list[dict[str, Any]] | None:
    redis_client = create_redis_client()
    try:
        raw_payload = redis_client.get(leaderboard_scoreboard_cache_key(run_id))
        if raw_payload is None:
            return None
        return _parse_cached_row_list(raw_payload)
    except Exception:  # noqa: BLE001
        return None
    finally:
        redis_client.close()


def write_leaderboard_scoreboard_cache(
    run_id: uuid.UUID,
    entries: list[dict[str, Any]],
) -> None:
    serialized_entries = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    redis_client = create_redis_client()
    try:
        redis_client.set(
            leaderboard_scoreboard_cache_key(run_id),
            serialized_entries,
            ex=max(1, load_leaderboard_cache_ttl_seconds()),
        )
    except Exception:  # noqa: BLE001
        return
    finally:
        redis_client.close()


def invalidate_leaderboard_scoreboard_cache(run_id: uuid.UUID) -> None:
    redis_client = create_redis_client()
    try:
        redis_client.delete(leaderboard_scoreboard_cache_key(run_id))
    except Exception:  # noqa: BLE001
        return
    finally:
        redis_client.close()


def write_leaderboard_cursor_snapshot(
    run_id: uuid.UUID,
    snapshot_id: str,
    entries: list[dict[str, Any]],
) -> None:
    serialized_entries = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    redis_client = create_redis_client()
    try:
        redis_client.set(
            leaderboard_cursor_snapshot_cache_key(run_id, snapshot_id),
            serialized_entries,
            ex=max(1, load_leaderboard_cursor_snapshot_ttl_seconds()),
        )
    except Exception:  # noqa: BLE001
        return
    finally:
        redis_client.close()


def read_leaderboard_cursor_snapshot(run_id: uuid.UUID, snapshot_id: str) -> list[dict[str, Any]] | None:
    redis_client = create_redis_client()
    try:
        raw_payload = redis_client.get(leaderboard_cursor_snapshot_cache_key(run_id, snapshot_id))
        if raw_payload is None:
            return None
        return _parse_cached_row_list(raw_payload)
    except Exception:  # noqa: BLE001
        return None
    finally:
        redis_client.close()
