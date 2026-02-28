from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, ArtifactType, RunState, SubmissionState
from app.db.models import Agent, Artifact, BaselineIdeaVector, Challenge, Run, Submission
from app.scoring.final_score import ScoreComponents, compose_final_score
from app.scoring.similarity import build_submission_similarity_vector, cosine_similarity, score_submission_similarity
from app.scoring.too_safe import score_too_safe_penalty
from app.scoring.weights import DEFAULT_WEIGHTS


@pytest.mark.asyncio
async def test_similarity_and_too_safe_penalties_compose_into_weighted_penalties(session: AsyncSession) -> None:
    challenge = Challenge(
        title="Penalty composition test",
        prompt="Build a small MVP with clear novelty against baseline ideas.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(
        challenge_id=challenge.id,
        state=RunState.RUNNING,
        started_at=datetime(2026, 2, 28, 0, 0, tzinfo=UTC),
        config_snapshot={},
    )
    session.add(run)
    await session.flush()

    first_agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="hacker-a")
    second_agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="hacker-b")
    session.add_all([first_agent, second_agent])
    await session.flush()

    first_submission = Submission(
        run_id=run.id,
        agent_id=first_agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Use deterministic triage heuristics to reduce response latency.",
        summary="Deterministic triage workflow that ranks urgent tickets first.",
    )
    second_submission = Submission(
        run_id=run.id,
        agent_id=second_agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Use deterministic triage heuristics to reduce response latency.",
        summary="Deterministic triage workflow that ranks urgent tickets first.",
    )
    session.add_all([first_submission, second_submission])
    await session.flush()

    content_hash = "f" * 64
    session.add_all(
        [
            Artifact(
                submission_id=first_submission.id,
                artifact_type=ArtifactType.API_SERVICE,
                storage_key="first/api.py",
                content_hash=content_hash,
            ),
            Artifact(
                submission_id=second_submission.id,
                artifact_type=ArtifactType.API_SERVICE,
                storage_key="second/api.py",
                content_hash=content_hash,
            ),
        ]
    )
    await session.flush()

    baseline_vector = build_submission_similarity_vector(first_submission.summary, [content_hash])
    session.add(
        BaselineIdeaVector(
            run_id=run.id,
            idea_index=0,
            idea_text="Reference baseline",
            vector=baseline_vector,
            prompt_template="baseline-prompt",
        )
    )
    await session.commit()

    similarity_score = await score_submission_similarity(session, first_submission.id)
    too_safe_score = await score_too_safe_penalty(session, first_submission.id)
    expected_similarity = cosine_similarity(baseline_vector, baseline_vector)

    assert similarity_score.max_similarity == pytest.approx(expected_similarity, abs=1e-6)
    assert too_safe_score.too_safe_penalty == pytest.approx(expected_similarity, abs=1e-6)

    breakdown = compose_final_score(
        ScoreComponents(
            quality=0.9,
            novelty=0.8,
            feasibility=0.7,
            criteria=0.6,
            similarity_penalty=similarity_score.max_similarity,
            too_safe_penalty=too_safe_score.too_safe_penalty,
            non_production_penalty=0.0,
        ),
        DEFAULT_WEIGHTS,
    )
    expected_penalties = (
        similarity_score.max_similarity * DEFAULT_WEIGHTS.similarity_penalty
        + too_safe_score.too_safe_penalty * DEFAULT_WEIGHTS.too_safe_penalty
    )
    assert breakdown.weighted_penalties == pytest.approx(expected_penalties, abs=1e-6)
