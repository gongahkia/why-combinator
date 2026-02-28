from __future__ import annotations

import json
from datetime import UTC, datetime

from app.queue.budget import create_redis_client


DEAD_LETTER_QUEUE_KEY = "queue:dead_letter"


def persist_dead_letter_event(
    task_name: str,
    run_id: str,
    reason: str,
    retries: int,
) -> None:
    redis_client = create_redis_client()
    try:
        payload = {
            "task_name": task_name,
            "run_id": run_id,
            "reason": reason,
            "retries": retries,
            "failed_at": datetime.now(UTC).isoformat(),
        }
        redis_client.rpush(DEAD_LETTER_QUEUE_KEY, json.dumps(payload))
    finally:
        redis_client.close()
