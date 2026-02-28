from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.challenges import ChallengeCreateRequest, create_challenge
from app.api.leaderboard import get_leaderboard, get_leaderboard_paginated
from app.api.runs import RunStartRequest, start_run
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, LeaderboardEntry, Run, Submission


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str | int] = {}

    async def setnx(self, key: str, value: int) -> bool:
        if key in self.kv:
            return False
        self.kv[key] = value
        return True


@pytest.mark.asyncio
async def test_start_run_persists_segmentation_labels_in_config_snapshot(session: AsyncSession) -> None:
    challenge = await create_challenge(
        ChallengeCreateRequest(
            title="Segmented run setup",
            prompt="Segment run results by team and track labels.",
            iteration_window_seconds=1800,
            minimum_quality_threshold=0.1,
            risk_appetite="balanced",
            complexity_slider=0.4,
        ),
        _rate_limit=None,
        session=session,
    )

    fake_request = SimpleNamespace(
        state=SimpleNamespace(quota_user_id="segment-user"),
        app=SimpleNamespace(
            state=SimpleNamespace(
                redis=_FakeAsyncRedis(),
                settings=SimpleNamespace(default_run_budget_units=100, artifact_storage_path="/tmp/hackathon-artifacts"),
            )
        ),
    )
    run = await start_run(
        challenge.id,
        request=fake_request,
        payload=RunStartRequest(team_label="red-team", track_label="enterprise"),
        _rate_limit=None,
        session=session,
    )

    assert run.config_snapshot["segmentation"] == {"team": "red-team", "track": "enterprise"}


@pytest.mark.asyncio
async def test_leaderboard_filters_and_groups_by_run_segmentation_labels(session: AsyncSession) -> None:
    challenge = Challenge(
        title="Leaderboard segmentation",
        prompt="Filter leaderboard by run segmentation labels.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.2,
        risk_appetite="balanced",
        complexity_slider=0.5,
    )
    session.add(challenge)
    await session.flush()

    run = Run(
        challenge_id=challenge.id,
        state=RunState.RUNNING,
        started_at=datetime.now(UTC),
        config_snapshot={"segmentation": {"team": "red-team", "track": "enterprise"}},
    )
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="segmented-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.ACCEPTED,
        value_hypothesis="Segment labels should drive leaderboard filtering.",
        summary="Segmented leaderboard submission.",
        accepted_at=datetime.now(UTC),
    )
    session.add(submission)
    await session.flush()

    session.add(
        LeaderboardEntry(
            run_id=run.id,
            submission_id=submission.id,
            rank=1,
            final_score=0.92,
            tie_break_metadata={},
        )
    )
    await session.commit()

    filtered = await get_leaderboard(
        run.id,
        team="red-team",
        track="enterprise",
        group_by="team",
        session=session,
    )
    assert filtered.grouped_by == "team"
    assert filtered.group_key == "red-team"
    assert len(filtered.items) == 1
    assert filtered.items[0].segment_labels == {"team": "red-team", "track": "enterprise"}

    excluded = await get_leaderboard(
        run.id,
        team="blue-team",
        session=session,
    )
    assert excluded.items == []

    paginated = await get_leaderboard_paginated(
        run.id,
        limit=5,
        cursor=None,
        team="blue-team",
        group_by="track",
        session=session,
    )
    assert paginated.items == []
    assert paginated.has_more is False
    assert paginated.grouped_by == "track"
    assert paginated.group_key == "enterprise"
