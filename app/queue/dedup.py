from __future__ import annotations

import os
import uuid

import redis


def create_redis_client() -> redis.Redis:
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)


def score_job_dedup_key(submission_id: uuid.UUID, checkpoint_id: str) -> str:
    return f"score-job:{submission_id}:{checkpoint_id}"


def claim_score_job_dedup_key(
    redis_client: redis.Redis,
    submission_id: uuid.UUID,
    checkpoint_id: str,
    ttl_seconds: int = 3600,
) -> bool:
    return bool(
        redis_client.set(
            score_job_dedup_key(submission_id, checkpoint_id),
            "1",
            nx=True,
            ex=ttl_seconds,
        )
    )
