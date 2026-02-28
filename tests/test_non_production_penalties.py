from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, Run, Submission
from app.scoring.penalties import generate_non_production_penalties, load_non_production_penalty_multiplier, load_non_production_penalty_value


@pytest.mark.asyncio
async def test_non_production_penalty_applied_only_to_agents_without_accepted_submission(
    session: AsyncSession,
) -> None:
    challenge = Challenge(
        title="Penalty assignment test",
        prompt="Build an MVP that proves an execution path end to end.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(
        challenge_id=challenge.id,
        state=RunState.COMPLETED,
        started_at=datetime(2026, 2, 28, 0, 0, tzinfo=UTC),
        ended_at=datetime(2026, 2, 28, 1, 0, tzinfo=UTC),
        config_snapshot={},
    )
    session.add(run)
    await session.flush()

    producing_agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="producer")
    non_producing_agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="non-producer")
    session.add_all([producing_agent, non_producing_agent])
    await session.flush()

    session.add_all(
        [
            Submission(
                run_id=run.id,
                agent_id=producing_agent.id,
                state=SubmissionState.ACCEPTED,
                value_hypothesis="Accepted MVP hypothesis",
                summary="Accepted MVP summary",
            ),
            Submission(
                run_id=run.id,
                agent_id=non_producing_agent.id,
                state=SubmissionState.REJECTED,
                value_hypothesis="Rejected MVP hypothesis",
                summary="Rejected MVP summary",
            ),
        ]
    )
    await session.commit()

    created_penalties = await generate_non_production_penalties(session, run.id, checkpoint_id="run_end")
    await session.commit()
    assert len(created_penalties) == 1

    expected_value = load_non_production_penalty_value() * load_non_production_penalty_multiplier()
    penalty = created_penalties[0]
    assert penalty.penalty_type == "non_production"
    assert penalty.checkpoint_id == "run_end"
    assert penalty.value == pytest.approx(expected_value, abs=1e-9)

    # Second pass should not duplicate the same penalty event.
    second_pass = await generate_non_production_penalties(session, run.id, checkpoint_id="run_end")
    assert second_pass == []
