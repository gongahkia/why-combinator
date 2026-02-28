from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.realtime import compute_leaderboard_deltas, fetch_realtime_run_state
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, CheckpointSnapshot, LeaderboardEntry, Run, Submission


@pytest.mark.asyncio
async def test_compute_leaderboard_deltas_detects_added_updated_and_removed() -> None:
    previous = {
        "submission-a": (1, 0.8),
        "submission-b": (2, 0.6),
    }
    current_rows = [
        {"rank": 1, "submission_id": "submission-c", "final_score": 0.9},
        {"rank": 2, "submission_id": "submission-a", "final_score": 0.7},
    ]

    deltas = compute_leaderboard_deltas(previous, current_rows)
    by_submission = {row["submission_id"]: row for row in deltas}

    assert by_submission["submission-c"]["change_type"] == "added"
    assert by_submission["submission-a"]["change_type"] == "updated"
    assert by_submission["submission-a"]["rank_delta"] == 1
    assert by_submission["submission-a"]["score_delta"] == pytest.approx(-0.1, abs=1e-6)
    assert by_submission["submission-b"]["change_type"] == "removed"


@pytest.mark.asyncio
async def test_fetch_realtime_run_state_returns_latest_checkpoint_and_limited_leaderboard(
    session: AsyncSession,
) -> None:
    challenge = Challenge(
        title="Realtime stream test",
        prompt="Stream checkpoint and leaderboard updates.",
        iteration_window_seconds=900,
        minimum_quality_threshold=0.2,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(
        challenge_id=challenge.id,
        state=RunState.RUNNING,
        started_at=datetime(2026, 2, 28, 0, 0, tzinfo=UTC),
        config_snapshot={},
    )
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="realtime-agent")
    session.add(agent)
    await session.flush()

    submission_a = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Submission A hypothesis for realtime stream testing.",
        summary="Submission A summary.",
    )
    submission_b = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Submission B hypothesis for realtime stream testing.",
        summary="Submission B summary.",
    )
    session.add_all([submission_a, submission_b])
    await session.flush()

    session.add_all(
        [
            CheckpointSnapshot(
                run_id=run.id,
                checkpoint_id="checkpoint:old",
                captured_at=datetime(2026, 2, 28, 0, 5, tzinfo=UTC),
                active_weights={"quality": 0.35},
                active_policies={"policy": "old"},
            ),
            CheckpointSnapshot(
                run_id=run.id,
                checkpoint_id="checkpoint:new",
                captured_at=datetime(2026, 2, 28, 0, 6, tzinfo=UTC),
                active_weights={"quality": 0.4},
                active_policies={"policy": "new"},
            ),
            LeaderboardEntry(
                run_id=run.id,
                submission_id=submission_a.id,
                rank=1,
                final_score=0.9,
                tie_break_metadata={},
            ),
            LeaderboardEntry(
                run_id=run.id,
                submission_id=submission_b.id,
                rank=2,
                final_score=0.8,
                tie_break_metadata={},
            ),
        ]
    )
    await session.commit()

    state = await fetch_realtime_run_state(session, run.id, max_entries=1)

    checkpoint = state["checkpoint"]
    assert checkpoint is not None
    assert checkpoint["checkpoint_id"] == "checkpoint:new"
    assert len(state["leaderboard"]) == 1
    assert state["leaderboard"][0]["rank"] == 1
