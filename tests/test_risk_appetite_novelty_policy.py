from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, Run, ScoreEvent, Submission
from app.orchestrator.policy import apply_risk_appetite_novelty_penalty_sensitivity
from app.scoring.anti_gaming import AntiGamingScore
from app.scoring.checkpoint import run_checkpoint_scoring_worker
from app.scoring.similarity import SimilarityScore
from app.scoring.too_safe import TooSafePenaltyScore


def test_risk_appetite_novelty_policy_adjusts_penalty_sensitivity() -> None:
    conservative = apply_risk_appetite_novelty_penalty_sensitivity("conservative", 0.3, 0.3)
    balanced = apply_risk_appetite_novelty_penalty_sensitivity("balanced", 0.3, 0.3)
    aggressive = apply_risk_appetite_novelty_penalty_sensitivity("aggressive", 0.3, 0.3)

    assert conservative[0] > balanced[0] > aggressive[0]
    assert conservative[1] > balanced[1] > aggressive[1]


@pytest.mark.asyncio
async def test_checkpoint_scoring_applies_risk_appetite_novelty_thresholds(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenge = Challenge(
        title="Risk appetite novelty policy test",
        prompt="Aggressive profile should reduce novelty penalties.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.0,
        risk_appetite="aggressive",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, started_at=datetime.now(UTC), config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="policy-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Risk appetite should tune novelty sensitivity.",
        summary="Novelty policy checkpoint submission.",
    )
    session.add(submission)
    await session.commit()

    async def _fake_run_judge_scoring_worker(*args, **kwargs) -> int:  # noqa: ANN002, ANN003
        return 0

    async def _fake_score_submission_quality(*args, **kwargs) -> float:  # noqa: ANN002, ANN003
        return 0.9

    async def _fake_score_submission_similarity(*args, **kwargs) -> SimilarityScore:  # noqa: ANN002, ANN003
        return SimilarityScore(
            submission_id=submission.id,
            max_similarity=0.5,
            compared_submissions=1,
        )

    async def _fake_detect_template_clone_penalty(*args, **kwargs) -> AntiGamingScore:  # noqa: ANN002, ANN003
        return AntiGamingScore(
            submission_id=submission.id,
            penalty=0.0,
            matched_submission_id=None,
            compared_submissions=0,
        )

    async def _fake_score_too_safe_penalty(*args, **kwargs) -> TooSafePenaltyScore:  # noqa: ANN002, ANN003
        return TooSafePenaltyScore(
            submission_id=submission.id,
            too_safe_penalty=0.5,
            compared_baselines=1,
        )

    async def _fake_apply_quality_threshold_gate(*args, **kwargs) -> bool:  # noqa: ANN002, ANN003
        return True

    async def _fake_materialize_leaderboard(*args, **kwargs) -> list[object]:  # noqa: ANN002, ANN003
        return []

    monkeypatch.setattr("app.scoring.checkpoint.run_judge_scoring_worker", _fake_run_judge_scoring_worker)
    monkeypatch.setattr("app.scoring.checkpoint.score_submission_quality", _fake_score_submission_quality)
    monkeypatch.setattr("app.scoring.checkpoint.score_submission_similarity", _fake_score_submission_similarity)
    monkeypatch.setattr("app.scoring.checkpoint.detect_template_clone_penalty", _fake_detect_template_clone_penalty)
    monkeypatch.setattr("app.scoring.checkpoint.score_too_safe_penalty", _fake_score_too_safe_penalty)
    monkeypatch.setattr("app.scoring.checkpoint.apply_quality_threshold_gate", _fake_apply_quality_threshold_gate)
    monkeypatch.setattr("app.scoring.checkpoint.materialize_leaderboard", _fake_materialize_leaderboard)

    await run_checkpoint_scoring_worker(
        session,
        run.id,
        trace_id="policy-trace",
        score_time=datetime(2026, 2, 28, 0, 0, tzinfo=UTC),
    )

    score_stmt: Select[tuple[ScoreEvent]] = (
        select(ScoreEvent).where(ScoreEvent.submission_id == submission.id).order_by(ScoreEvent.created_at.desc()).limit(1)
    )
    score_event = (await session.execute(score_stmt)).scalar_one()

    components = score_event.payload["components"]
    assert components["similarity_penalty"] == pytest.approx(0.3, abs=1e-6)
    assert components["too_safe_penalty"] == pytest.approx(0.3, abs=1e-6)
    assert score_event.payload["raw_similarity_penalty"] == pytest.approx(0.5, abs=1e-6)
    assert score_event.payload["raw_too_safe_penalty"] == pytest.approx(0.5, abs=1e-6)
