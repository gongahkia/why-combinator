from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.artifacts import validate_submission_mandatory_requirements
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, Run, Submission


@pytest.mark.asyncio
async def test_mandatory_submission_validator_rejects_incomplete_submission(session: AsyncSession) -> None:
    challenge = Challenge(
        title="Mandatory validator test",
        prompt="Build an MVP with runnable output and documentation.",
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

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="validator-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="",
        summary="Submission missing required pieces.",
    )
    session.add(submission)
    await session.commit()

    fake_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(artifact_storage_path="/tmp"))))
    result = await validate_submission_mandatory_requirements(submission.id, fake_request, session)
    assert result.valid is False
    assert "value_hypothesis is required" in result.errors
    assert "at least one runnable artifact is required" in result.errors
    assert "README artifact is required" in result.errors
