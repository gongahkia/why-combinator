from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.analytics import get_replay_diff_metrics
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, CheckpointSnapshot, Run, ScoreEvent, Submission
from app.scoring.events import compute_score_event_payload_checksum
from app.scoring.final_score import ActiveWeightsSnapshot, ScoreComponents


@pytest.mark.asyncio
async def test_replay_diff_endpoint_returns_score_deltas_and_rank_shift(session: AsyncSession) -> None:
    challenge = Challenge(
        title="Replay diff analytics test",
        prompt="Compare original and replay scores.",
        iteration_window_seconds=1200,
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
        config_snapshot={"challenge": {"id": str(challenge.id), "title": challenge.title}},
    )
    session.add(run)
    await session.flush()

    agent_a = Agent(run_id=run.id, role=AgentRole.HACKER, name="agent-a")
    agent_b = Agent(run_id=run.id, role=AgentRole.HACKER, name="agent-b")
    session.add_all([agent_a, agent_b])
    await session.flush()

    submission_a = Submission(
        run_id=run.id,
        agent_id=agent_a.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Submission A hypothesis.",
        summary="Submission A summary for replay diff.",
    )
    submission_b = Submission(
        run_id=run.id,
        agent_id=agent_b.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Submission B hypothesis.",
        summary="Submission B summary for replay diff.",
    )
    session.add_all([submission_a, submission_b])
    await session.flush()

    checkpoint_id = "checkpoint:diff"
    weights = ActiveWeightsSnapshot(
        quality=1.0,
        novelty=0.0,
        feasibility=0.0,
        criteria=0.0,
        similarity_penalty=0.0,
        too_safe_penalty=0.0,
        non_production_penalty=0.0,
    )
    session.add(
        CheckpointSnapshot(
            run_id=run.id,
            checkpoint_id=checkpoint_id,
            captured_at=datetime(2026, 2, 28, 0, 5, tzinfo=UTC),
            active_weights=asdict(weights),
            active_policies={},
        )
    )

    components_a = ScoreComponents(
        quality=0.8,
        novelty=0.0,
        feasibility=0.0,
        criteria=0.0,
        similarity_penalty=0.0,
        too_safe_penalty=0.0,
        non_production_penalty=0.0,
    )
    payload_a = {"components": asdict(components_a), "weights": asdict(weights)}

    components_b = ScoreComponents(
        quality=0.7,
        novelty=0.0,
        feasibility=0.0,
        criteria=0.0,
        similarity_penalty=0.0,
        too_safe_penalty=0.0,
        non_production_penalty=0.0,
    )
    payload_b = {"components": asdict(components_b), "weights": asdict(weights)}

    session.add_all(
        [
            ScoreEvent(
                submission_id=submission_a.id,
                checkpoint_id=checkpoint_id,
                quality_score=0.8,
                novelty_score=0.0,
                feasibility_score=0.0,
                criteria_score=0.0,
                final_score=0.6,
                payload=payload_a,
                payload_checksum=compute_score_event_payload_checksum(payload_a),
            ),
            ScoreEvent(
                submission_id=submission_b.id,
                checkpoint_id=checkpoint_id,
                quality_score=0.7,
                novelty_score=0.0,
                feasibility_score=0.0,
                criteria_score=0.0,
                final_score=0.9,
                payload=payload_b,
                payload_checksum=compute_score_event_payload_checksum(payload_b),
            ),
        ]
    )
    await session.commit()

    response = await get_replay_diff_metrics(run.id, checkpoint_id=checkpoint_id, session=session)

    assert response.run_id == run.id
    assert response.checkpoint_id == checkpoint_id
    assert len(response.submissions) == 2

    by_submission = {item.submission_id: item for item in response.submissions}
    assert by_submission[submission_a.id].delta == pytest.approx(0.2, abs=1e-6)
    assert by_submission[submission_a.id].direction == "up"
    assert by_submission[submission_a.id].original_rank == 2
    assert by_submission[submission_a.id].replay_rank == 1
    assert by_submission[submission_a.id].rank_shift == -1

    assert by_submission[submission_b.id].delta == pytest.approx(-0.2, abs=1e-6)
    assert by_submission[submission_b.id].direction == "down"
    assert by_submission[submission_b.id].original_rank == 1
    assert by_submission[submission_b.id].replay_rank == 2
    assert by_submission[submission_b.id].rank_shift == 1
