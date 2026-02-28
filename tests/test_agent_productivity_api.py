from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.analytics import get_agent_productivity_metrics
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, PenaltyEvent, Run, Submission


@pytest.mark.asyncio
async def test_agent_productivity_endpoint_returns_attempts_accepts_and_penalties(
    session: AsyncSession,
) -> None:
    challenge = Challenge(
        title="Agent productivity API test",
        prompt="Measure per-agent attempts, accepted submissions, and penalties.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, started_at=datetime.now(UTC), config_snapshot={})
    session.add(run)
    await session.flush()

    agent_a = Agent(run_id=run.id, role=AgentRole.HACKER, name="agent-a")
    agent_b = Agent(run_id=run.id, role=AgentRole.HACKER, name="agent-b")
    session.add_all([agent_a, agent_b])
    await session.flush()

    submission_a1 = Submission(
        run_id=run.id,
        agent_id=agent_a.id,
        state=SubmissionState.ACCEPTED,
        value_hypothesis="Reduce incident response time by 20% in 2 weeks.",
        summary="Accepted submission from agent-a.",
        accepted_at=datetime.now(UTC),
    )
    submission_a2 = Submission(
        run_id=run.id,
        agent_id=agent_a.id,
        state=SubmissionState.REJECTED,
        value_hypothesis="Improve runbook quality by 15% over 1 month.",
        summary="Rejected submission from agent-a.",
    )
    submission_b1 = Submission(
        run_id=run.id,
        agent_id=agent_b.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Increase triage throughput by 10% in 7 days.",
        summary="Pending submission from agent-b.",
    )
    session.add_all([submission_a1, submission_a2, submission_b1])
    await session.flush()

    session.add_all(
        [
            PenaltyEvent(
                submission_id=submission_a2.id,
                checkpoint_id="cp",
                source="test",
                penalty_type="similarity",
                value=0.2,
                explanation="similarity penalty",
            ),
            PenaltyEvent(
                submission_id=submission_b1.id,
                checkpoint_id="cp",
                source="test",
                penalty_type="too_safe",
                value=0.1,
                explanation="too-safe penalty",
            ),
        ]
    )
    await session.commit()

    response = await get_agent_productivity_metrics(run.id, session=session)

    assert response.run_id == run.id
    assert len(response.metrics) == 2

    top = response.metrics[0]
    assert top.agent_id == agent_a.id
    assert top.attempts == 2
    assert top.accepted_mvps == 1
    assert top.penalties == 1
    assert top.penalty_total == pytest.approx(0.2, abs=1e-6)

    second = response.metrics[1]
    assert second.agent_id == agent_b.id
    assert second.attempts == 1
    assert second.accepted_mvps == 0
    assert second.penalties == 1
    assert second.penalty_total == pytest.approx(0.1, abs=1e-6)
