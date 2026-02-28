from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, Run, ScoreEvent, Submission
from app.orchestrator.policy import resolve_artifact_sophistication_policy
from app.scoring.anti_gaming import AntiGamingScore
from app.scoring.checkpoint import run_checkpoint_scoring_worker
from app.scoring.similarity import SimilarityScore
from app.scoring.sophistication import evaluate_artifact_sophistication_rubric
from app.scoring.too_safe import TooSafePenaltyScore


def test_complexity_slider_scales_artifact_sophistication_target() -> None:
    low = resolve_artifact_sophistication_policy(0.0)
    high = resolve_artifact_sophistication_policy(1.0)

    assert high.target_sophistication > low.target_sophistication
    assert high.tolerance < low.tolerance


def test_artifact_sophistication_rubric_penalizes_simple_artifacts_for_high_complexity() -> None:
    low_complexity = evaluate_artifact_sophistication_rubric([], complexity_slider=0.0)
    high_complexity = evaluate_artifact_sophistication_rubric([], complexity_slider=1.0)

    assert low_complexity.rubric_score > high_complexity.rubric_score


@pytest.mark.asyncio
async def test_checkpoint_scoring_blends_complexity_sophistication_into_criteria_score(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenge = Challenge(
        title="Complexity sophistication checkpoint test",
        prompt="Complexity slider should influence expected artifact sophistication.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.0,
        risk_appetite="balanced",
        complexity_slider=1.0,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, started_at=datetime.now(UTC), config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="complexity-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Complexity should raise sophistication expectations.",
        summary="No artifacts submitted to maximize sophistication gap.",
    )
    session.add(submission)
    await session.commit()

    async def _fake_run_judge_scoring_worker(*args, **kwargs) -> int:  # noqa: ANN002, ANN003
        return 0

    async def _fake_score_submission_quality(*args, **kwargs) -> float:  # noqa: ANN002, ANN003
        return 1.0

    async def _fake_score_submission_similarity(*args, **kwargs) -> SimilarityScore:  # noqa: ANN002, ANN003
        return SimilarityScore(submission_id=submission.id, max_similarity=0.0, compared_submissions=0)

    async def _fake_detect_template_clone_penalty(*args, **kwargs) -> AntiGamingScore:  # noqa: ANN002, ANN003
        return AntiGamingScore(submission_id=submission.id, penalty=0.0, matched_submission_id=None, compared_submissions=0)

    async def _fake_score_too_safe_penalty(*args, **kwargs) -> TooSafePenaltyScore:  # noqa: ANN002, ANN003
        return TooSafePenaltyScore(submission_id=submission.id, too_safe_penalty=0.0, compared_baselines=0)

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
        trace_id="complexity-trace",
        score_time=datetime(2026, 2, 28, 0, 0, tzinfo=UTC),
    )

    score_stmt: Select[tuple[ScoreEvent]] = (
        select(ScoreEvent).where(ScoreEvent.submission_id == submission.id).order_by(ScoreEvent.created_at.desc()).limit(1)
    )
    event = (await session.execute(score_stmt)).scalar_one()

    criteria_score = event.payload["components"]["criteria"]
    assert criteria_score < 1.0
    assert event.payload["artifact_sophistication"]["expected_sophistication"] > 0.8
