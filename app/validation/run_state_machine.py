from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.db.enums import RunState
from app.db.models import Run


@dataclass(frozen=True)
class RunStateTransitionError(Exception):
    current_state: RunState
    target_state: RunState

    def __str__(self) -> str:
        return f"illegal run state transition: {self.current_state.value} -> {self.target_state.value}"


LEGAL_RUN_STATE_TRANSITIONS: dict[RunState, set[RunState]] = {
    RunState.CREATED: {RunState.RUNNING, RunState.FAILED, RunState.CANCELED},
    RunState.RUNNING: {RunState.CANCELING, RunState.COMPLETED, RunState.FAILED},
    RunState.CANCELING: {RunState.CANCELED, RunState.FAILED},
    RunState.COMPLETED: set(),
    RunState.CANCELED: set(),
    RunState.FAILED: set(),
}


def assert_run_state_transition(current: RunState, target: RunState) -> None:
    if current == target:
        return
    allowed = LEGAL_RUN_STATE_TRANSITIONS.get(current, set())
    if target in allowed:
        return
    raise RunStateTransitionError(current_state=current, target_state=target)


def apply_run_state_transition(
    run: Run,
    target_state: RunState,
    now: datetime | None = None,
) -> None:
    assert_run_state_transition(run.state, target_state)
    if run.state == target_state:
        return
    run.state = target_state
    current_time = now or datetime.now(UTC)
    if target_state == RunState.RUNNING and run.started_at is None:
        run.started_at = current_time
    if target_state in {RunState.COMPLETED, RunState.CANCELED, RunState.FAILED}:
        run.ended_at = current_time
