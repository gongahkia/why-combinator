from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, JudgeProfile, JudgeScore, Run, Submission
from app.scoring.quality import JudgeRubricOutput, score_quality_rubric, score_submission_quality


def test_quality_rubric_outlier_dampener_reduces_outlier_influence() -> None:
    outputs = [
        JudgeRubricOutput(judge_profile_id=uuid.uuid4(), score=0.95, rubric_weight=1.0),
        JudgeRubricOutput(judge_profile_id=uuid.uuid4(), score=0.9, rubric_weight=1.0),
        JudgeRubricOutput(judge_profile_id=uuid.uuid4(), score=0.1, rubric_weight=1.0),
    ]
    dampened = score_quality_rubric(outputs)
    naive_average = round((0.95 + 0.9 + 0.1) / 3.0, 6)

    assert dampened > naive_average
    assert dampened < 0.95


@pytest.mark.asyncio
async def test_score_submission_quality_applies_outlier_dampener_from_judge_scores(
    session: AsyncSession,
) -> None:
    challenge = Challenge(
        title="Judge outlier dampener test",
        prompt="Protect quality scoring from single-judge outliers.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    judge_profiles = [
        JudgeProfile(
            challenge_id=challenge.id,
            domain="product",
            scoring_style="balanced",
            profile_prompt="Judge product quality.",
            head_judge=False,
            source_type="inline_json",
        ),
        JudgeProfile(
            challenge_id=challenge.id,
            domain="engineering",
            scoring_style="balanced",
            profile_prompt="Judge engineering quality.",
            head_judge=False,
            source_type="inline_json",
        ),
        JudgeProfile(
            challenge_id=challenge.id,
            domain="risk",
            scoring_style="balanced",
            profile_prompt="Judge risk quality.",
            head_judge=False,
            source_type="inline_json",
        ),
    ]
    session.add_all(judge_profiles)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="outlier-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Reduce cost by 15% in 3 weeks.",
        summary="Judge outlier dampener submission.",
    )
    session.add(submission)
    await session.flush()

    scores = [0.95, 0.9, 0.1]
    for profile, score in zip(judge_profiles, scores, strict=True):
        session.add(
            JudgeScore(
                submission_id=submission.id,
                judge_profile_id=profile.id,
                checkpoint_id="cp-outlier",
                score=score,
                rationale=f"score={score}",
                raw_response={},
            )
        )
    await session.commit()

    quality_score = await score_submission_quality(session, submission.id, checkpoint_id="cp-outlier")
    naive_average = round(sum(scores) / len(scores), 6)

    assert quality_score > naive_average
    assert quality_score < 0.95
