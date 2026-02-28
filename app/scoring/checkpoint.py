from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, Challenge, Run, ScoreEvent, Submission
from app.judging.worker import run_judge_scoring_worker
from app.leaderboard.materializer import materialize_leaderboard
from app.scoring.anti_gaming import detect_template_clone_penalty
from app.scoring.checkpoint_snapshot import capture_checkpoint_snapshot
from app.scoring.events import create_score_event_idempotent
from app.scoring.feasibility import RuntimeValidationSignal, score_feasibility
from app.scoring.final_score import ScoreComponents, compose_final_score
from app.scoring.novelty_normalization import normalize_novelty_score
from app.scoring.penalty_events import create_penalty_event_append_only
from app.scoring.quality import score_submission_quality
from app.scoring.similarity import score_submission_similarity
from app.scoring.threshold import apply_quality_threshold_gate
from app.scoring.too_safe import score_too_safe_penalty
from app.scoring.weights import resolve_active_weights_snapshot


@dataclass(frozen=True)
class CheckpointScoringResult:
    checkpoint_id: str
    scored_submissions: int
    skipped_submissions: int
    judge_scores_created: int
    leaderboard_entries: int


def _checkpoint_id(timestamp: datetime) -> str:
    return f"checkpoint:{timestamp.strftime('%Y%m%dT%H%M%SZ')}"


def _build_effective_config_checksum(
    active_weights: dict[str, float],
    active_policies: dict[str, object],
) -> str:
    normalized = json.dumps(
        {"weights": active_weights, "policies": active_policies},
        sort_keys=True,
        separators=(",", ":"),
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, normalized))


async def _load_latest_score_event(session: AsyncSession, submission_id: uuid.UUID) -> ScoreEvent | None:
    stmt: Select[tuple[ScoreEvent]] = (
        select(ScoreEvent)
        .where(ScoreEvent.submission_id == submission_id)
        .order_by(ScoreEvent.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _persist_submission_checkpoint_writes_atomic(
    session: AsyncSession,
    *,
    submission_id: uuid.UUID,
    checkpoint_id: str,
    quality_score: float,
    novelty_score: float,
    feasibility_score: float,
    criteria_score: float,
    final_score: float,
    payload: dict[str, object],
    anti_gaming_penalty: float,
    anti_gaming_matched_submission_id: uuid.UUID | None,
) -> None:
    async with session.begin_nested():
        await create_score_event_idempotent(
            session=session,
            submission_id=submission_id,
            checkpoint_id=checkpoint_id,
            quality_score=quality_score,
            novelty_score=novelty_score,
            feasibility_score=feasibility_score,
            criteria_score=criteria_score,
            final_score=final_score,
            payload=payload,
            idempotency_key=f"checkpoint-score:{checkpoint_id}:{submission_id}",
        )
        if anti_gaming_penalty > 0:
            await create_penalty_event_append_only(
                session=session,
                submission_id=submission_id,
                checkpoint_id=checkpoint_id,
                source="anti_gaming_detector",
                penalty_type="template_clone_shallow_mutation",
                value=anti_gaming_penalty,
                explanation=(
                    "submission text shows high overlap with peer submission "
                    f"{anti_gaming_matched_submission_id}"
                ),
            )


async def run_checkpoint_scoring_worker(
    session: AsyncSession,
    run_id: uuid.UUID,
    trace_id: str | None = None,
    score_time: datetime | None = None,
) -> CheckpointScoringResult:
    now = score_time or datetime.now(UTC)
    checkpoint_id = _checkpoint_id(now)

    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError("run not found")
    challenge = await session.get(Challenge, run.challenge_id)
    if challenge is None:
        raise ValueError("challenge not found")

    active_weights_snapshot = await resolve_active_weights_snapshot(session, run_id, now)
    active_weights = asdict(active_weights_snapshot)
    active_policies: dict[str, object] = {
        "risk_appetite": challenge.risk_appetite,
        "complexity_slider": challenge.complexity_slider,
        "minimum_quality_threshold": challenge.minimum_quality_threshold,
    }
    effective_config_checksum = _build_effective_config_checksum(active_weights, active_policies)
    await capture_checkpoint_snapshot(
        session=session,
        run_id=run_id,
        checkpoint_id=checkpoint_id,
        active_weights=active_weights,
        active_policies=active_policies,
    )

    submission_stmt: Select[tuple[Submission]] = select(Submission).where(Submission.run_id == run_id)
    submissions = (await session.execute(submission_stmt)).scalars().all()
    submissions_to_score: list[Submission] = []
    skipped_submissions = 0
    for submission in submissions:
        latest_event = await _load_latest_score_event(session, submission.id)
        latest_checksum = ""
        if latest_event is not None and isinstance(latest_event.payload, dict):
            checksum_value = latest_event.payload.get("effective_config_checksum")
            if isinstance(checksum_value, str):
                latest_checksum = checksum_value
        if latest_checksum == effective_config_checksum:
            skipped_submissions += 1
            continue
        submissions_to_score.append(submission)

    judge_scores_created = 0
    if submissions_to_score:
        judge_scores_created = await run_judge_scoring_worker(
            session,
            run_id,
            checkpoint_id=checkpoint_id,
            submission_ids={submission.id for submission in submissions_to_score},
            trace_id=trace_id,
        )

    scored_submissions = 0
    for submission in submissions_to_score:
        artifact_count_stmt: Select[tuple[int]] = (
            select(func.count()).select_from(Artifact).where(Artifact.submission_id == submission.id)
        )
        artifact_count = (await session.execute(artifact_count_stmt)).scalar_one()
        quality_score = await score_submission_quality(session, submission.id, checkpoint_id=checkpoint_id)
        similarity_score = await score_submission_similarity(session, submission.id)
        anti_gaming_score = await detect_template_clone_penalty(session, submission.id)
        too_safe_score = await score_too_safe_penalty(session, submission.id)
        novelty_score = normalize_novelty_score(1.0 - similarity_score.max_similarity)
        combined_similarity_penalty = max(similarity_score.max_similarity, anti_gaming_score.penalty)
        feasibility_score = score_feasibility(
            runtime_signals=[
                RuntimeValidationSignal(
                    validator_type="artifact_presence",
                    outcome="passed" if artifact_count > 0 else "failed",
                )
            ],
            dependency_resolution_log="",
        )
        criteria_score = quality_score
        quality_gate_passed = await apply_quality_threshold_gate(session, submission.id, quality_score)

        components = ScoreComponents(
            quality=quality_score,
            novelty=novelty_score,
            feasibility=feasibility_score,
            criteria=criteria_score,
            similarity_penalty=combined_similarity_penalty,
            too_safe_penalty=too_safe_score.too_safe_penalty,
            non_production_penalty=0.0,
        )
        breakdown = compose_final_score(components, active_weights_snapshot)
        payload = breakdown.as_payload()
        payload["effective_config_checksum"] = effective_config_checksum
        payload["quality_gate_passed"] = quality_gate_passed
        payload["trace_id"] = trace_id or ""
        payload["anti_gaming_penalty"] = anti_gaming_score.penalty
        payload["anti_gaming_matched_submission_id"] = (
            str(anti_gaming_score.matched_submission_id) if anti_gaming_score.matched_submission_id else None
        )

        await _persist_submission_checkpoint_writes_atomic(
            session,
            submission_id=submission.id,
            checkpoint_id=checkpoint_id,
            quality_score=quality_score,
            novelty_score=novelty_score,
            feasibility_score=feasibility_score,
            criteria_score=criteria_score,
            final_score=breakdown.final_score,
            payload=payload,
            anti_gaming_penalty=anti_gaming_score.penalty,
            anti_gaming_matched_submission_id=anti_gaming_score.matched_submission_id,
        )
        await session.commit()
        scored_submissions += 1

    leaderboard_entries = await materialize_leaderboard(session, run_id)
    await session.commit()
    return CheckpointScoringResult(
        checkpoint_id=checkpoint_id,
        scored_submissions=scored_submissions,
        skipped_submissions=skipped_submissions,
        judge_scores_created=judge_scores_created,
        leaderboard_entries=len(leaderboard_entries),
    )
