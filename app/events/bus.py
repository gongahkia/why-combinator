from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

from redis.asyncio import Redis


@dataclass(frozen=True)
class RunLifecycleEvent:
    event_type: Literal["run_started", "run_completed", "run_canceled", "run_failed"]
    run_id: str
    challenge_id: str
    occurred_at: str
    payload: dict[str, object]


@dataclass(frozen=True)
class ScoringLifecycleEvent:
    event_type: Literal["score_queued", "score_computed", "score_persisted", "penalty_applied"]
    run_id: str
    submission_id: str
    checkpoint_id: str
    occurred_at: str
    payload: dict[str, object]


def make_run_lifecycle_event(
    event_type: Literal["run_started", "run_completed", "run_canceled", "run_failed"],
    run_id: uuid.UUID,
    challenge_id: uuid.UUID,
    payload: dict[str, object],
) -> RunLifecycleEvent:
    return RunLifecycleEvent(
        event_type=event_type,
        run_id=str(run_id),
        challenge_id=str(challenge_id),
        occurred_at=datetime.now(UTC).isoformat(),
        payload=payload,
    )


def make_scoring_lifecycle_event(
    event_type: Literal["score_queued", "score_computed", "score_persisted", "penalty_applied"],
    run_id: uuid.UUID,
    submission_id: uuid.UUID,
    checkpoint_id: str,
    payload: dict[str, object],
) -> ScoringLifecycleEvent:
    return ScoringLifecycleEvent(
        event_type=event_type,
        run_id=str(run_id),
        submission_id=str(submission_id),
        checkpoint_id=checkpoint_id,
        occurred_at=datetime.now(UTC).isoformat(),
        payload=payload,
    )


async def emit_run_event(redis_client: Redis, event: RunLifecycleEvent) -> None:
    await redis_client.publish("run_events", json.dumps(asdict(event)))


async def emit_scoring_event(redis_client: Redis, event: ScoringLifecycleEvent) -> None:
    await redis_client.publish("scoring_events", json.dumps(asdict(event)))
