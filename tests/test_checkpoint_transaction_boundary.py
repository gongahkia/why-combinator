from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, PenaltyEvent, Run, ScoreEvent, Submission
from app.scoring.checkpoint import _persist_submission_checkpoint_writes_atomic


async def _seed_submission(session: AsyncSession) -> Submission:
    challenge = Challenge(
        title="Checkpoint transaction boundary test",
        prompt="Ensure score and penalty writes are atomic per submission.",
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

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="tx-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Atomic writes prevent partial checkpoint persistence.",
        summary="Checkpoint transactional boundary submission.",
    )
    session.add(submission)
    await session.commit()
    return submission


@pytest.mark.asyncio
async def test_checkpoint_atomic_writes_roll_back_score_when_penalty_insert_fails(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submission = await _seed_submission(session)

    async def _raise_penalty_failure(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("penalty insert failed")

    monkeypatch.setattr("app.scoring.checkpoint.create_penalty_event_append_only", _raise_penalty_failure)

    with pytest.raises(RuntimeError, match="penalty insert failed"):
        await _persist_submission_checkpoint_writes_atomic(
            session,
            submission_id=submission.id,
            checkpoint_id="checkpoint:tx-failure",
            quality_score=0.8,
            novelty_score=0.8,
            feasibility_score=0.8,
            criteria_score=0.8,
            final_score=0.8,
            payload={"source": "tx-test"},
            anti_gaming_penalty=0.4,
            anti_gaming_matched_submission_id=submission.id,
        )

    score_count_stmt: Select[tuple[int]] = (
        select(func.count()).select_from(ScoreEvent).where(ScoreEvent.submission_id == submission.id)
    )
    penalty_count_stmt: Select[tuple[int]] = (
        select(func.count()).select_from(PenaltyEvent).where(PenaltyEvent.submission_id == submission.id)
    )
    score_count = (await session.execute(score_count_stmt)).scalar_one()
    penalty_count = (await session.execute(penalty_count_stmt)).scalar_one()

    assert score_count == 0
    assert penalty_count == 0
