from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, Run, ScoreEvent, Submission
from app.scoring.anti_gaming import AntiGamingScore
from app.scoring.artifact_overlap import ArtifactOverlapScore
from app.scoring.checkpoint import run_checkpoint_scoring_worker
from app.scoring.novelty_strategy import resolve_novelty_strategy_mode
from app.scoring.similarity import SimilarityScore
from app.scoring.too_safe import TooSafePenaltyScore


def test_resolve_novelty_strategy_mode_defaults_to_embedding_only() -> None:
    assert resolve_novelty_strategy_mode("hybrid_overlap") == "hybrid_overlap"
    assert resolve_novelty_strategy_mode("embedding_only") == "embedding_only"
    assert resolve_novelty_strategy_mode("unexpected-value") == "embedding_only"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("strategy_mode", "expected_raw_similarity", "expected_artifact_overlap"),
    [
        ("embedding_only", 0.2, 0.0),
        ("hybrid_overlap", 0.9, 0.9),
    ],
)
async def test_checkpoint_scoring_respects_configured_novelty_strategy(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    strategy_mode: str,
    expected_raw_similarity: float,
    expected_artifact_overlap: float,
) -> None:
    challenge = Challenge(
        title="Novelty strategy selector test",
        prompt="Select novelty strategy between embedding-only and hybrid overlap.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.0,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, started_at=datetime.now(UTC), config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name=f"strategy-agent-{strategy_mode}")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Novelty strategy should alter overlap penalties.",
        summary="Novelty strategy selector submission.",
    )
    session.add(submission)
    await session.commit()

    async def _fake_run_judge_scoring_worker(*args, **kwargs) -> int:  # noqa: ANN002, ANN003
        return 0

    async def _fake_score_submission_quality(*args, **kwargs) -> float:  # noqa: ANN002, ANN003
        return 0.8

    async def _fake_score_submission_similarity(*args, **kwargs) -> SimilarityScore:  # noqa: ANN002, ANN003
        return SimilarityScore(submission_id=submission.id, max_similarity=0.2, compared_submissions=1)

    async def _fake_score_artifact_overlap(*args, **kwargs) -> ArtifactOverlapScore:  # noqa: ANN002, ANN003
        return ArtifactOverlapScore(submission_id=submission.id, max_overlap=0.9, compared_submissions=1)

    async def _fake_detect_template_clone_penalty(*args, **kwargs) -> AntiGamingScore:  # noqa: ANN002, ANN003
        return AntiGamingScore(
            submission_id=submission.id,
            penalty=0.0,
            matched_submission_id=None,
            compared_submissions=0,
        )

    async def _fake_score_too_safe_penalty(*args, **kwargs) -> TooSafePenaltyScore:  # noqa: ANN002, ANN003
        return TooSafePenaltyScore(submission_id=submission.id, too_safe_penalty=0.0, compared_baselines=1)

    async def _fake_apply_quality_threshold_gate(*args, **kwargs) -> bool:  # noqa: ANN002, ANN003
        return True

    async def _fake_materialize_leaderboard(*args, **kwargs) -> list[object]:  # noqa: ANN002, ANN003
        return []

    monkeypatch.setattr("app.scoring.checkpoint.load_settings", lambda: SimpleNamespace(
        artifact_storage_path=str(tmp_path),
        novelty_strategy_mode=strategy_mode,
    ))
    monkeypatch.setattr("app.scoring.checkpoint.run_judge_scoring_worker", _fake_run_judge_scoring_worker)
    monkeypatch.setattr("app.scoring.checkpoint.score_submission_quality", _fake_score_submission_quality)
    monkeypatch.setattr("app.scoring.checkpoint.score_submission_similarity", _fake_score_submission_similarity)
    monkeypatch.setattr("app.scoring.checkpoint.score_artifact_overlap", _fake_score_artifact_overlap)
    monkeypatch.setattr("app.scoring.checkpoint.detect_template_clone_penalty", _fake_detect_template_clone_penalty)
    monkeypatch.setattr("app.scoring.checkpoint.score_too_safe_penalty", _fake_score_too_safe_penalty)
    monkeypatch.setattr("app.scoring.checkpoint.apply_quality_threshold_gate", _fake_apply_quality_threshold_gate)
    monkeypatch.setattr("app.scoring.checkpoint.materialize_leaderboard", _fake_materialize_leaderboard)

    await run_checkpoint_scoring_worker(
        session,
        run.id,
        trace_id="strategy-trace",
        score_time=datetime(2026, 2, 28, 0, 0, tzinfo=UTC),
    )

    score_stmt: Select[tuple[ScoreEvent]] = (
        select(ScoreEvent).where(ScoreEvent.submission_id == submission.id).order_by(ScoreEvent.created_at.desc()).limit(1)
    )
    score_event = (await session.execute(score_stmt)).scalar_one()

    assert score_event.payload["novelty_strategy_mode"] == strategy_mode
    assert score_event.payload["raw_embedding_similarity_penalty"] == pytest.approx(0.2, abs=1e-6)
    assert score_event.payload["raw_artifact_overlap_penalty"] == pytest.approx(expected_artifact_overlap, abs=1e-6)
    assert score_event.payload["raw_similarity_penalty"] == pytest.approx(expected_raw_similarity, abs=1e-6)
