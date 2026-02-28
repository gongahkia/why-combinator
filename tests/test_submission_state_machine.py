from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.submissions import SubmissionStateTransitionRequest, transition_submission_state
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, Run, Submission
from app.scoring.threshold import apply_quality_threshold_gate
from app.validation.submission_state_machine import (
    SubmissionStateTransitionError,
    apply_submission_state_transition,
)


def test_submission_state_machine_rejects_illegal_transition() -> None:
    submission = Submission(
        run_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        state=SubmissionState.ACCEPTED,
        value_hypothesis="Reduce latency by 20% within 1 week.",
        summary="state machine test",
    )
    with pytest.raises(SubmissionStateTransitionError):
        apply_submission_state_transition(submission, SubmissionState.PENDING)


@pytest.mark.asyncio
async def test_transition_endpoint_rejects_invalid_submission_state_transition(
    session: AsyncSession,
) -> None:
    challenge = Challenge(
        title="Submission state transition test",
        prompt="Validate legal state transitions for submissions.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="transition-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.ACCEPTED,
        value_hypothesis="Increase throughput by 15% in 7 days.",
        summary="Submission used for invalid transition endpoint test.",
        accepted_at=datetime.now(UTC),
    )
    session.add(submission)
    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await transition_submission_state(
            run.id,
            submission.id,
            SubmissionStateTransitionRequest(state=SubmissionState.PENDING),
            session=session,
        )
    assert exc_info.value.status_code == 422
    assert "illegal submission state transition" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_quality_threshold_gate_applies_legal_scored_to_terminal_transitions(
    session: AsyncSession,
) -> None:
    challenge = Challenge(
        title="Submission scoring transition test",
        prompt="Create score event and verify scored transition.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, config_snapshot={})
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="score-transition-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.ACCEPTED,
        value_hypothesis="Reduce costs by 10% in 30 days.",
        summary="Scored transition submission.",
        accepted_at=datetime.now(UTC),
    )
    session.add(submission)
    await session.commit()

    accepted = await apply_quality_threshold_gate(session, submission.id, quality_score=0.1)
    await session.commit()
    await session.refresh(submission)

    assert accepted is False
    assert submission.state == SubmissionState.REJECTED
    assert submission.accepted_at is None
