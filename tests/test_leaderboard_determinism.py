from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, PenaltyEvent, Run, ScoreEvent, Submission
from app.leaderboard.materializer import materialize_leaderboard


@pytest.mark.asyncio
async def test_leaderboard_order_is_deterministic_with_equal_scores_and_tie_breaks(session: AsyncSession) -> None:
    start = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    challenge = Challenge(
        title="Leaderboard determinism test",
        prompt="Build comparable MVPs for deterministic ranking.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.5,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(challenge_id=challenge.id, state=RunState.RUNNING, started_at=start, config_snapshot={})
    session.add(run)
    await session.flush()

    agents = [
        Agent(run_id=run.id, role=AgentRole.HACKER, name="a"),
        Agent(run_id=run.id, role=AgentRole.HACKER, name="b"),
        Agent(run_id=run.id, role=AgentRole.HACKER, name="c"),
        Agent(run_id=run.id, role=AgentRole.HACKER, name="d"),
    ]
    session.add_all(agents)
    await session.flush()

    submission_ids = [
        uuid.UUID("00000000-0000-0000-0000-0000000000a1"),
        uuid.UUID("00000000-0000-0000-0000-0000000000b2"),
        uuid.UUID("00000000-0000-0000-0000-0000000000c3"),
        uuid.UUID("00000000-0000-0000-0000-0000000000d4"),
    ]
    accepted_early = start + timedelta(minutes=1)
    accepted_late = start + timedelta(minutes=2)
    submissions = [
        Submission(
            id=submission_ids[0],
            run_id=run.id,
            agent_id=agents[0].id,
            state=SubmissionState.ACCEPTED,
            value_hypothesis="vh-a",
            summary="summary-a",
            accepted_at=accepted_early,
        ),
        Submission(
            id=submission_ids[1],
            run_id=run.id,
            agent_id=agents[1].id,
            state=SubmissionState.ACCEPTED,
            value_hypothesis="vh-b",
            summary="summary-b",
            accepted_at=accepted_late,
        ),
        Submission(
            id=submission_ids[2],
            run_id=run.id,
            agent_id=agents[2].id,
            state=SubmissionState.ACCEPTED,
            value_hypothesis="vh-c",
            summary="summary-c",
            accepted_at=accepted_late,
        ),
        Submission(
            id=submission_ids[3],
            run_id=run.id,
            agent_id=agents[3].id,
            state=SubmissionState.ACCEPTED,
            value_hypothesis="vh-d",
            summary="summary-d",
            accepted_at=accepted_late,
        ),
    ]
    session.add_all(submissions)
    await session.flush()

    for submission in submissions:
        session.add(
            ScoreEvent(
                submission_id=submission.id,
                checkpoint_id="cp",
                quality_score=0.8,
                novelty_score=0.8,
                feasibility_score=0.8,
                criteria_score=0.8,
                final_score=0.8,
                payload={"source": "test"},
                payload_checksum=f"checksum-{submission.id}",
            )
        )

    # b has lower penalty than c/d, while c and d tie on penalty and accepted_at.
    session.add_all(
        [
            PenaltyEvent(
                submission_id=submission_ids[1],
                checkpoint_id="cp",
                source="test",
                penalty_type="similarity",
                value=0.2,
                explanation="penalty-b",
            ),
            PenaltyEvent(
                submission_id=submission_ids[2],
                checkpoint_id="cp",
                source="test",
                penalty_type="similarity",
                value=0.5,
                explanation="penalty-c",
            ),
            PenaltyEvent(
                submission_id=submission_ids[3],
                checkpoint_id="cp",
                source="test",
                penalty_type="similarity",
                value=0.5,
                explanation="penalty-d",
            ),
        ]
    )
    await session.commit()

    entries = await materialize_leaderboard(session, run.id)
    await session.commit()

    ranked_submission_ids = [entry.submission_id for entry in sorted(entries, key=lambda row: row.rank)]
    assert ranked_submission_ids == [
        submission_ids[0],  # earliest accepted_at
        submission_ids[1],  # lower total penalty among same accepted_at
        submission_ids[2],  # equal penalty/accepted_at -> lower submission_id
        submission_ids[3],
    ]

    metadata_stmt: Select[tuple[dict[str, object]]] = select(ScoreEvent.payload).where(
        ScoreEvent.submission_id == submission_ids[0]
    )
    metadata_payload = (await session.execute(metadata_stmt)).scalar_one()
    assert metadata_payload == {"source": "test"}
