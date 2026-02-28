from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.runs import RunStateTransitionRequest, transition_run_state
from app.api.submissions import SubmissionStateTransitionRequest, transition_submission_state
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, Run, Submission


@pytest.mark.asyncio
async def test_illegal_run_and_submission_transitions_are_rejected_integration(
    session: AsyncSession,
) -> None:
    challenge = Challenge(
        title="State machine integration test",
        prompt="Reject illegal run and submission state transitions.",
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
        started_at=datetime.now(UTC),
        config_snapshot={},
    )
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="state-machine-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.ACCEPTED,
        value_hypothesis="Illegal transitions should fail validation.",
        summary="Integrated illegal transition submission.",
        accepted_at=datetime.now(UTC),
    )
    session.add(submission)
    await session.commit()

    with pytest.raises(HTTPException) as run_exc:
        await transition_run_state(
            challenge.id,
            run.id,
            RunStateTransitionRequest(state=RunState.CREATED),
            _rate_limit=None,
            session=session,
        )
    assert run_exc.value.status_code == 422
    assert "illegal run state transition" in str(run_exc.value.detail)

    with pytest.raises(HTTPException) as submission_exc:
        await transition_submission_state(
            run.id,
            submission.id,
            SubmissionStateTransitionRequest(state=SubmissionState.PENDING),
            session=session,
        )
    assert submission_exc.value.status_code == 422
    assert "illegal submission state transition" in str(submission_exc.value.detail)

    refreshed_run = await session.get(Run, run.id)
    refreshed_submission = await session.get(Submission, submission.id)
    assert refreshed_run is not None
    assert refreshed_run.state == RunState.RUNNING
    assert refreshed_submission is not None
    assert refreshed_submission.state == SubmissionState.ACCEPTED
