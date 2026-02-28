from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.runs import RunStateTransitionRequest, cancel_run, transition_run_state
from app.db.enums import RunState
from app.db.models import Challenge, Run
from app.validation.run_state_machine import RunStateTransitionError, apply_run_state_transition


def test_run_state_machine_rejects_illegal_transition() -> None:
    run = Run(
        challenge_id=uuid.uuid4(),
        state=RunState.COMPLETED,
        config_snapshot={},
    )
    with pytest.raises(RunStateTransitionError):
        apply_run_state_transition(run, RunState.RUNNING)


@pytest.mark.asyncio
async def test_transition_run_state_endpoint_rejects_invalid_transition(
    session: AsyncSession,
) -> None:
    challenge = Challenge(
        title="Run transition test",
        prompt="Validate run transition requests.",
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
    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await transition_run_state(
            challenge.id,
            run.id,
            RunStateTransitionRequest(state=RunState.CREATED),
            _rate_limit=None,
            session=session,
        )
    assert exc_info.value.status_code == 422
    assert "illegal run state transition" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_cancel_run_transitions_through_canceling_to_canceled(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenge = Challenge(
        title="Run cancel transition test",
        prompt="Cancel path should enforce legal run transitions.",
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
    await session.commit()

    monkeypatch.setattr("app.api.runs._kill_active_run_containers", lambda _: [])
    monkeypatch.setattr("app.api.runs._revoke_run_tasks", lambda _: [])

    response = await cancel_run(
        challenge.id,
        run.id,
        _rate_limit=None,
        session=session,
    )

    assert response.state == RunState.CANCELED
    refreshed = await session.get(Run, run.id)
    assert refreshed is not None
    assert refreshed.state == RunState.CANCELED
