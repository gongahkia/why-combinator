from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, Run, ScoreEvent, ScoringWeightConfig, Submission
from app.scoring.checkpoint import run_checkpoint_scoring_worker


@pytest.mark.asyncio
async def test_forward_config_change_only_rescores_after_activation(session: AsyncSession) -> None:
    base_time = datetime(2026, 2, 28, 0, 0, tzinfo=UTC)
    challenge = Challenge(
        title="Forward config scoring test",
        prompt="Build an MVP that helps teams triage support tickets faster.",
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
        started_at=base_time,
        config_snapshot={},
    )
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="hacker-one")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Automated triage can cut first-response time by 40 percent.",
        summary="A support triage assistant that classifies urgency and routes to the right queue.",
    )
    session.add(submission)
    await session.commit()

    first_result = await run_checkpoint_scoring_worker(session, run.id, score_time=base_time)
    assert first_result.scored_submissions == 1

    session.add(
        ScoringWeightConfig(
            run_id=run.id,
            effective_from=base_time + timedelta(hours=2),
            weights={
                "quality": 0.4,
                "novelty": 0.2,
                "feasibility": 0.2,
                "criteria": 0.2,
                "similarity_penalty": 0.3,
                "too_safe_penalty": 0.1,
            },
        )
    )
    await session.commit()

    second_result = await run_checkpoint_scoring_worker(
        session,
        run.id,
        score_time=base_time + timedelta(hours=1),
    )
    assert second_result.scored_submissions == 0
    assert second_result.skipped_submissions == 1

    third_result = await run_checkpoint_scoring_worker(
        session,
        run.id,
        score_time=base_time + timedelta(hours=3),
    )
    assert third_result.scored_submissions == 1

    events_stmt: Select[tuple[ScoreEvent]] = (
        select(ScoreEvent)
        .where(ScoreEvent.submission_id == submission.id)
        .order_by(ScoreEvent.created_at.asc(), ScoreEvent.id.asc())
    )
    events = (await session.execute(events_stmt)).scalars().all()
    assert len(events) == 2
    assert events[0].payload["effective_config_checksum"] != events[1].payload["effective_config_checksum"]
