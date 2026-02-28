from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.idempotency import (
    get_idempotent_response,
    hash_request_payload,
    store_idempotent_response,
)
from app.db.models import ScoreEvent, Submission
from app.leaderboard.cache import invalidate_leaderboard_scoreboard_cache


def compute_score_event_payload_checksum(payload: dict[str, object]) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


async def create_score_event_idempotent(
    session: AsyncSession,
    submission_id: uuid.UUID,
    checkpoint_id: str,
    quality_score: float,
    novelty_score: float,
    feasibility_score: float,
    criteria_score: float,
    final_score: float,
    payload: dict[str, object],
    idempotency_key: str,
) -> ScoreEvent:
    request_payload = {
        "submission_id": str(submission_id),
        "checkpoint_id": checkpoint_id,
        "quality_score": quality_score,
        "novelty_score": novelty_score,
        "feasibility_score": feasibility_score,
        "criteria_score": criteria_score,
        "final_score": final_score,
        "payload": payload,
    }
    request_hash = hash_request_payload(request_payload)
    scope = f"score_event_write:{submission_id}:{checkpoint_id}"
    existing = await get_idempotent_response(session, scope, idempotency_key, request_hash)
    if existing is not None:
        score_event_id = uuid.UUID(existing["score_event_id"])
        row = await session.get(ScoreEvent, score_event_id)
        if row is None:
            raise ValueError("idempotent score event references missing row")
        return row

    score_event = ScoreEvent(
        submission_id=submission_id,
        checkpoint_id=checkpoint_id,
        quality_score=quality_score,
        novelty_score=novelty_score,
        feasibility_score=feasibility_score,
        criteria_score=criteria_score,
        final_score=final_score,
        payload=payload,
        payload_checksum=compute_score_event_payload_checksum(payload),
    )
    session.add(score_event)
    await session.flush()
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise ValueError("score event submission not found")
    invalidate_leaderboard_scoreboard_cache(submission.run_id)
    await store_idempotent_response(
        session,
        scope,
        idempotency_key,
        request_hash,
        {"score_event_id": str(score_event.id)},
    )
    return score_event
