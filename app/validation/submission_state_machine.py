from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.db.enums import SubmissionState
from app.db.models import Submission


@dataclass(frozen=True)
class SubmissionStateTransitionError(Exception):
    current_state: SubmissionState
    target_state: SubmissionState

    def __str__(self) -> str:
        return f"illegal submission state transition: {self.current_state.value} -> {self.target_state.value}"


LEGAL_SUBMISSION_STATE_TRANSITIONS: dict[SubmissionState, set[SubmissionState]] = {
    SubmissionState.PENDING: {SubmissionState.SCORED, SubmissionState.REJECTED},
    SubmissionState.SCORED: {SubmissionState.ACCEPTED, SubmissionState.REJECTED},
    SubmissionState.ACCEPTED: {SubmissionState.SCORED},
    SubmissionState.REJECTED: {SubmissionState.SCORED},
}


def assert_submission_state_transition(current: SubmissionState, target: SubmissionState) -> None:
    if current == target:
        return
    allowed = LEGAL_SUBMISSION_STATE_TRANSITIONS.get(current, set())
    if target in allowed:
        return
    raise SubmissionStateTransitionError(current_state=current, target_state=target)


def apply_submission_state_transition(
    submission: Submission,
    target_state: SubmissionState,
    now: datetime | None = None,
) -> None:
    assert_submission_state_transition(submission.state, target_state)
    if submission.state == target_state:
        return
    submission.state = target_state
    current_time = now or datetime.now(UTC)
    if target_state == SubmissionState.ACCEPTED:
        submission.accepted_at = current_time
    else:
        submission.accepted_at = None
