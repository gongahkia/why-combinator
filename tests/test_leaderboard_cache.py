from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.leaderboard import get_leaderboard
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, PenaltyEvent, Run, ScoreEvent, Submission
from app.leaderboard.materializer import materialize_leaderboard
from app.scoring.events import create_score_event_idempotent
from app.scoring.penalty_events import create_penalty_event_append_only


async def _seed_run_with_submission(session: AsyncSession) -> tuple[Run, Submission]:
    challenge = Challenge(
        title="Leaderboard cache test",
        prompt="Cache leaderboard rows and invalidate on score changes.",
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

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="cache-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.ACCEPTED,
        value_hypothesis="Cache invalidation keeps leaderboard fresh.",
        summary="Submission used for leaderboard cache tests.",
        accepted_at=datetime.now(UTC),
    )
    session.add(submission)
    await session.commit()
    return run, submission


@pytest.mark.asyncio
async def test_materialize_leaderboard_writes_scoreboard_cache(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, submission = await _seed_run_with_submission(session)
    session.add(
        ScoreEvent(
            submission_id=submission.id,
            checkpoint_id="cp",
            quality_score=0.7,
            novelty_score=0.8,
            feasibility_score=0.9,
            criteria_score=0.75,
            final_score=0.8,
            payload={"source": "cache-test"},
            payload_checksum="checksum-cache-materialize",
        )
    )
    await session.commit()

    observed: dict[str, object] = {}

    def _fake_write(run_id, rows) -> None:
        observed["run_id"] = run_id
        observed["rows"] = rows

    monkeypatch.setattr("app.leaderboard.materializer.write_leaderboard_scoreboard_cache", _fake_write)

    await materialize_leaderboard(session, run.id)

    assert observed["run_id"] == run.id
    rows = observed["rows"]
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0]["rank"] == 1
    assert rows[0]["submission_id"] == str(submission.id)


@pytest.mark.asyncio
async def test_score_event_insert_invalidates_scoreboard_cache(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, submission = await _seed_run_with_submission(session)
    invalidated: list[str] = []

    monkeypatch.setattr(
        "app.scoring.events.invalidate_leaderboard_scoreboard_cache",
        lambda run_id: invalidated.append(str(run_id)),
    )

    await create_score_event_idempotent(
        session=session,
        submission_id=submission.id,
        checkpoint_id="cp-score",
        quality_score=0.8,
        novelty_score=0.8,
        feasibility_score=0.8,
        criteria_score=0.8,
        final_score=0.8,
        payload={"trace_id": "cache-invalidate-score"},
        idempotency_key="score-cache-invalidate",
    )

    assert invalidated == [str(run.id)]


@pytest.mark.asyncio
async def test_penalty_event_insert_invalidates_scoreboard_cache(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, submission = await _seed_run_with_submission(session)
    invalidated: list[str] = []

    monkeypatch.setattr(
        "app.scoring.penalty_events.invalidate_leaderboard_scoreboard_cache",
        lambda run_id: invalidated.append(str(run_id)),
    )

    await create_penalty_event_append_only(
        session=session,
        submission_id=submission.id,
        checkpoint_id="cp-penalty",
        source="test",
        penalty_type="similarity",
        value=0.2,
        explanation="cache invalidation test penalty",
    )

    assert invalidated == [str(run.id)]


@pytest.mark.asyncio
async def test_get_leaderboard_uses_cached_scoreboard_rows(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, submission = await _seed_run_with_submission(session)
    session.add(
        ScoreEvent(
            submission_id=submission.id,
            checkpoint_id="cp-api",
            quality_score=0.75,
            novelty_score=0.76,
            feasibility_score=0.77,
            criteria_score=0.78,
            final_score=0.79,
            payload={"quality_gate_passed": True},
            payload_checksum="checksum-cache-api",
        )
    )
    session.add(
        PenaltyEvent(
            submission_id=submission.id,
            checkpoint_id="cp-api",
            source="test",
            penalty_type="too_safe",
            value=0.1,
            explanation="cached-row penalty",
        )
    )
    await session.commit()

    monkeypatch.setattr(
        "app.api.leaderboard.read_leaderboard_scoreboard_cache",
        lambda _: [
            {
                "rank": 1,
                "submission_id": str(submission.id),
                "final_score": 0.79,
                "tie_break_metadata": {"submission_id": str(submission.id)},
            }
        ],
    )

    response = await get_leaderboard(run.id, session=session)

    assert len(response.items) == 1
    assert response.items[0].submission_id == submission.id
    assert response.items[0].rank == 1
    assert response.items[0].final_score == 0.79
