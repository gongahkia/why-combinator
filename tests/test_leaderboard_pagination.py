from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.leaderboard import get_leaderboard_paginated
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, Run, ScoreEvent, Submission
from app.leaderboard.materializer import materialize_leaderboard


async def _seed_ranked_leaderboard(session: AsyncSession) -> tuple[Run, list[Submission]]:
    start = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    challenge = Challenge(
        title="Leaderboard pagination test",
        prompt="Ensure pagination remains stable while scores update.",
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
    ]
    session.add_all(agents)
    await session.flush()

    submissions = [
        Submission(
            run_id=run.id,
            agent_id=agents[0].id,
            state=SubmissionState.ACCEPTED,
            value_hypothesis="vh-a",
            summary="summary-a",
            accepted_at=start + timedelta(minutes=1),
        ),
        Submission(
            run_id=run.id,
            agent_id=agents[1].id,
            state=SubmissionState.ACCEPTED,
            value_hypothesis="vh-b",
            summary="summary-b",
            accepted_at=start + timedelta(minutes=2),
        ),
        Submission(
            run_id=run.id,
            agent_id=agents[2].id,
            state=SubmissionState.ACCEPTED,
            value_hypothesis="vh-c",
            summary="summary-c",
            accepted_at=start + timedelta(minutes=3),
        ),
    ]
    session.add_all(submissions)
    await session.flush()

    for submission, final_score in zip(submissions, [0.9, 0.8, 0.7], strict=True):
        session.add(
            ScoreEvent(
                submission_id=submission.id,
                checkpoint_id="cp-initial",
                quality_score=final_score,
                novelty_score=final_score,
                feasibility_score=final_score,
                criteria_score=final_score,
                final_score=final_score,
                payload={"source": "seed"},
                payload_checksum=f"checksum-{submission.id}-initial",
            )
        )
    await session.commit()

    await materialize_leaderboard(session, run.id)
    await session.commit()
    return run, submissions


@pytest.mark.asyncio
async def test_paginated_leaderboard_cursor_remains_stable_across_score_updates(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, submissions = await _seed_ranked_leaderboard(session)
    snapshot_store: dict[tuple[str, str], list[dict[str, object]]] = {}

    monkeypatch.setattr("app.api.leaderboard.read_leaderboard_scoreboard_cache", lambda _: None)
    monkeypatch.setattr(
        "app.api.leaderboard.write_leaderboard_cursor_snapshot",
        lambda run_id, snapshot_id, entries: snapshot_store.__setitem__((str(run_id), snapshot_id), entries),
    )
    monkeypatch.setattr(
        "app.api.leaderboard.read_leaderboard_cursor_snapshot",
        lambda run_id, snapshot_id: snapshot_store.get((str(run_id), snapshot_id)),
    )

    first_page = await get_leaderboard_paginated(run.id, limit=2, cursor=None, session=session)
    assert [item.submission_id for item in first_page.items] == [submissions[0].id, submissions[1].id]
    assert first_page.next_cursor is not None
    assert first_page.has_more is True

    # Score update changes ranking, but cursor should still continue the original snapshot.
    session.add(
        ScoreEvent(
            submission_id=submissions[2].id,
            checkpoint_id="cp-updated",
            quality_score=0.99,
            novelty_score=0.99,
            feasibility_score=0.99,
            criteria_score=0.99,
            final_score=0.99,
            payload={"source": "updated"},
            payload_checksum=f"checksum-{submissions[2].id}-updated",
        )
    )
    await session.commit()
    await materialize_leaderboard(session, run.id)
    await session.commit()

    second_page = await get_leaderboard_paginated(
        run.id,
        limit=2,
        cursor=first_page.next_cursor,
        session=session,
    )

    assert [item.submission_id for item in second_page.items] == [submissions[2].id]
    assert second_page.next_cursor is None
    assert second_page.has_more is False


@pytest.mark.asyncio
async def test_paginated_leaderboard_rejects_expired_cursor_snapshot(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, _ = await _seed_ranked_leaderboard(session)
    snapshot_store: dict[tuple[str, str], list[dict[str, object]]] = {}

    monkeypatch.setattr("app.api.leaderboard.read_leaderboard_scoreboard_cache", lambda _: None)
    monkeypatch.setattr(
        "app.api.leaderboard.write_leaderboard_cursor_snapshot",
        lambda run_id, snapshot_id, entries: snapshot_store.__setitem__((str(run_id), snapshot_id), entries),
    )
    monkeypatch.setattr(
        "app.api.leaderboard.read_leaderboard_cursor_snapshot",
        lambda run_id, snapshot_id: snapshot_store.get((str(run_id), snapshot_id)),
    )

    first_page = await get_leaderboard_paginated(run.id, limit=1, cursor=None, session=session)
    assert first_page.next_cursor is not None

    snapshot_store.clear()

    with pytest.raises(HTTPException) as exc_info:
        await get_leaderboard_paginated(run.id, limit=1, cursor=first_page.next_cursor, session=session)

    assert exc_info.value.status_code == 410
