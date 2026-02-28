from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CheckpointSnapshot, Run, ScoreEvent, Submission
from app.scoring.final_score import ActiveWeightsSnapshot, ScoreComponentBounds, ScoreComponents, compose_final_score
from app.scoring.weights import DEFAULT_WEIGHTS


class ReplayNotFoundError(ValueError):
    pass


class ReplayValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ReplaySubmissionResult:
    submission_id: uuid.UUID
    original_final_score: float
    replay_final_score: float
    components: dict[str, float]


@dataclass(frozen=True)
class ReplayScoringResult:
    run_id: uuid.UUID
    checkpoint_id: str
    captured_at: datetime
    active_weights: dict[str, float]
    active_policies: dict[str, object]
    config_snapshot: dict[str, object]
    submissions: list[ReplaySubmissionResult]


def _coerce_float(value: object, name: str) -> float:
    if not isinstance(value, (int, float)):
        raise ReplayValidationError(f"{name} must be numeric")
    return float(value)


def _score_components_from_payload(payload: dict[str, object], submission_id: uuid.UUID) -> ScoreComponents:
    components_raw = payload.get("components")
    if not isinstance(components_raw, dict):
        raise ReplayValidationError(f"score payload missing components for submission {submission_id}")
    return ScoreComponents(
        quality=_coerce_float(components_raw.get("quality"), "components.quality"),
        novelty=_coerce_float(components_raw.get("novelty"), "components.novelty"),
        feasibility=_coerce_float(components_raw.get("feasibility"), "components.feasibility"),
        criteria=_coerce_float(components_raw.get("criteria"), "components.criteria"),
        similarity_penalty=_coerce_float(components_raw.get("similarity_penalty"), "components.similarity_penalty"),
        too_safe_penalty=_coerce_float(components_raw.get("too_safe_penalty"), "components.too_safe_penalty"),
        non_production_penalty=_coerce_float(
            components_raw.get("non_production_penalty", 0.0),
            "components.non_production_penalty",
        ),
    )


def _active_weights_snapshot(active_weights: dict[str, object]) -> ActiveWeightsSnapshot:
    return ActiveWeightsSnapshot(
        quality=float(active_weights.get("quality", DEFAULT_WEIGHTS.quality)),
        novelty=float(active_weights.get("novelty", DEFAULT_WEIGHTS.novelty)),
        feasibility=float(active_weights.get("feasibility", DEFAULT_WEIGHTS.feasibility)),
        criteria=float(active_weights.get("criteria", DEFAULT_WEIGHTS.criteria)),
        similarity_penalty=float(active_weights.get("similarity_penalty", DEFAULT_WEIGHTS.similarity_penalty)),
        too_safe_penalty=float(active_weights.get("too_safe_penalty", DEFAULT_WEIGHTS.too_safe_penalty)),
        non_production_penalty=float(
            active_weights.get("non_production_penalty", DEFAULT_WEIGHTS.non_production_penalty)
        ),
    )


def _score_component_bounds_from_policies(active_policies: dict[str, object]) -> ScoreComponentBounds | None:
    raw = active_policies.get("score_component_bounds")
    if not isinstance(raw, dict):
        return None
    try:
        return ScoreComponentBounds(
            quality_floor=float(raw["quality_floor"]),
            quality_cap=float(raw["quality_cap"]),
            novelty_floor=float(raw["novelty_floor"]),
            novelty_cap=float(raw["novelty_cap"]),
            feasibility_floor=float(raw["feasibility_floor"]),
            feasibility_cap=float(raw["feasibility_cap"]),
            criteria_floor=float(raw["criteria_floor"]),
            criteria_cap=float(raw["criteria_cap"]),
            similarity_penalty_floor=float(raw["similarity_penalty_floor"]),
            similarity_penalty_cap=float(raw["similarity_penalty_cap"]),
            too_safe_penalty_floor=float(raw["too_safe_penalty_floor"]),
            too_safe_penalty_cap=float(raw["too_safe_penalty_cap"]),
            non_production_penalty_floor=float(raw["non_production_penalty_floor"]),
            non_production_penalty_cap=float(raw["non_production_penalty_cap"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReplayValidationError("checkpoint score component bounds are malformed") from exc


async def _resolve_checkpoint_snapshot(
    session: AsyncSession,
    run_id: uuid.UUID,
    checkpoint_id: str | None,
) -> CheckpointSnapshot:
    if checkpoint_id is not None:
        stmt: Select[tuple[CheckpointSnapshot]] = (
            select(CheckpointSnapshot)
            .where(
                CheckpointSnapshot.run_id == run_id,
                CheckpointSnapshot.checkpoint_id == checkpoint_id,
            )
            .order_by(desc(CheckpointSnapshot.captured_at))
            .limit(1)
        )
    else:
        stmt = (
            select(CheckpointSnapshot)
            .where(CheckpointSnapshot.run_id == run_id)
            .order_by(desc(CheckpointSnapshot.captured_at))
            .limit(1)
        )
    snapshot = (await session.execute(stmt)).scalar_one_or_none()
    if snapshot is None:
        missing_id = checkpoint_id or "latest"
        raise ReplayNotFoundError(f"checkpoint snapshot not found: {missing_id}")
    return snapshot


async def replay_scoring_from_frozen_snapshot(
    session: AsyncSession,
    run_id: uuid.UUID,
    checkpoint_id: str | None = None,
) -> ReplayScoringResult:
    run = await session.get(Run, run_id)
    if run is None:
        raise ReplayNotFoundError("run not found")

    snapshot = await _resolve_checkpoint_snapshot(session, run_id, checkpoint_id)
    active_weights = snapshot.active_weights if isinstance(snapshot.active_weights, dict) else {}
    active_policies = snapshot.active_policies if isinstance(snapshot.active_policies, dict) else {}
    weights_snapshot = _active_weights_snapshot(active_weights)
    score_component_bounds = _score_component_bounds_from_policies(active_policies)

    events_stmt: Select[tuple[ScoreEvent]] = (
        select(ScoreEvent)
        .join(Submission, Submission.id == ScoreEvent.submission_id)
        .where(
            Submission.run_id == run_id,
            ScoreEvent.checkpoint_id == snapshot.checkpoint_id,
        )
        .order_by(desc(ScoreEvent.final_score), ScoreEvent.submission_id.asc())
    )
    score_events = (await session.execute(events_stmt)).scalars().all()
    if not score_events:
        raise ReplayNotFoundError(f"score events not found for checkpoint {snapshot.checkpoint_id}")

    replay_submissions: list[ReplaySubmissionResult] = []
    for score_event in score_events:
        payload = score_event.payload if isinstance(score_event.payload, dict) else {}
        components = _score_components_from_payload(payload, score_event.submission_id)
        replay_breakdown = compose_final_score(components, weights_snapshot, bounds=score_component_bounds)
        replay_submissions.append(
            ReplaySubmissionResult(
                submission_id=score_event.submission_id,
                original_final_score=score_event.final_score,
                replay_final_score=replay_breakdown.final_score,
                components={
                    key: float(value)
                    for key, value in asdict(replay_breakdown.components).items()
                },
            )
        )

    config_snapshot = run.config_snapshot if isinstance(run.config_snapshot, dict) else {}
    return ReplayScoringResult(
        run_id=run.id,
        checkpoint_id=snapshot.checkpoint_id,
        captured_at=snapshot.captured_at,
        active_weights={key: float(value) for key, value in asdict(weights_snapshot).items()},
        active_policies=active_policies,
        config_snapshot=config_snapshot,
        submissions=replay_submissions,
    )
