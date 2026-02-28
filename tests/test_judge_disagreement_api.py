from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.analytics import get_judge_disagreement_metrics
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, JudgeProfile, JudgeScore, Run, Submission


@pytest.mark.asyncio
async def test_judge_disagreement_endpoint_returns_per_judge_and_per_checkpoint_variance(
    session: AsyncSession,
) -> None:
    challenge = Challenge(
        title="Judge disagreement API test",
        prompt="Measure disagreement and variance for judge panel checkpoints.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    profile_a = JudgeProfile(
        challenge_id=challenge.id,
        domain="product",
        scoring_style="strict",
        profile_prompt="Judge product outcomes.",
        head_judge=False,
        source_type="inline_json",
    )
    profile_b = JudgeProfile(
        challenge_id=challenge.id,
        domain="engineering",
        scoring_style="balanced",
        profile_prompt="Judge engineering feasibility.",
        head_judge=True,
        source_type="inline_json",
    )
    session.add_all([profile_a, profile_b])
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="judge-metrics-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Increase conversion by 12% over 14 days.",
        summary="Judge disagreement submission.",
    )
    session.add(submission)
    await session.flush()

    session.add_all(
        [
            JudgeScore(
                submission_id=submission.id,
                judge_profile_id=profile_a.id,
                checkpoint_id="cp-1",
                score=0.9,
                rationale="High potential.",
                raw_response={},
            ),
            JudgeScore(
                submission_id=submission.id,
                judge_profile_id=profile_b.id,
                checkpoint_id="cp-1",
                score=0.3,
                rationale="Low confidence.",
                raw_response={},
            ),
            JudgeScore(
                submission_id=submission.id,
                judge_profile_id=profile_a.id,
                checkpoint_id="cp-2",
                score=0.8,
                rationale="Improved confidence.",
                raw_response={},
            ),
            JudgeScore(
                submission_id=submission.id,
                judge_profile_id=profile_b.id,
                checkpoint_id="cp-2",
                score=0.6,
                rationale="Still moderate.",
                raw_response={},
            ),
        ]
    )
    await session.commit()

    response = await get_judge_disagreement_metrics(run.id, session=session)

    assert response.run_id == run.id
    assert len(response.judge_metrics) == 2
    per_judge = {item.judge_profile_id: item for item in response.judge_metrics}
    assert per_judge[profile_a.id].mean_absolute_disagreement == pytest.approx(0.2, abs=1e-6)
    assert per_judge[profile_a.id].max_absolute_disagreement == pytest.approx(0.3, abs=1e-6)
    assert per_judge[profile_b.id].mean_absolute_disagreement == pytest.approx(0.2, abs=1e-6)
    assert per_judge[profile_b.id].max_absolute_disagreement == pytest.approx(0.3, abs=1e-6)

    variance_by_checkpoint = {item.checkpoint_id: item for item in response.checkpoint_variance}
    assert variance_by_checkpoint["cp-1"].inter_judge_variance == pytest.approx(0.09, abs=1e-6)
    assert variance_by_checkpoint["cp-2"].inter_judge_variance == pytest.approx(0.01, abs=1e-6)
