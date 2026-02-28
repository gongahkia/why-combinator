from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.scoring import ScoringReplayRequest, replay_run_scoring
from app.db.enums import AgentRole, RunState, SubmissionState
from app.db.models import Agent, Challenge, CheckpointSnapshot, Run, ScoreEvent, Submission
from app.orchestrator.reproducibility import REPLAY_SEED_ALGORITHM, derive_run_replay_seed
from app.scoring.events import compute_score_event_payload_checksum
from app.scoring.final_score import ActiveWeightsSnapshot, ScoreComponentBounds, ScoreComponents, compose_final_score


async def _seed_run_submission(session: AsyncSession) -> tuple[Run, Submission]:
    challenge = Challenge(
        title="Replay endpoint challenge",
        prompt="Replay scoring from frozen snapshots.",
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
        config_snapshot={"challenge": {"id": str(challenge.id), "title": challenge.title}},
    )
    session.add(run)
    await session.flush()

    agent = Agent(run_id=run.id, role=AgentRole.HACKER, name="replay-agent")
    session.add(agent)
    await session.flush()

    submission = Submission(
        run_id=run.id,
        agent_id=agent.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Replay should reproduce final scoring composition from frozen snapshots.",
        summary="Submission for replay endpoint test.",
    )
    session.add(submission)
    await session.flush()

    return run, submission


@pytest.mark.asyncio
async def test_replay_endpoint_recomputes_scores_from_frozen_snapshot(session: AsyncSession) -> None:
    run, submission = await _seed_run_submission(session)

    weights = ActiveWeightsSnapshot(
        quality=0.4,
        novelty=0.3,
        feasibility=0.2,
        criteria=0.1,
        similarity_penalty=0.25,
        too_safe_penalty=0.15,
        non_production_penalty=1.0,
    )
    bounds = ScoreComponentBounds(
        quality_floor=0.0,
        quality_cap=1.0,
        novelty_floor=0.0,
        novelty_cap=1.0,
        feasibility_floor=0.0,
        feasibility_cap=1.0,
        criteria_floor=0.0,
        criteria_cap=1.0,
        similarity_penalty_floor=0.0,
        similarity_penalty_cap=0.2,
        too_safe_penalty_floor=0.0,
        too_safe_penalty_cap=0.2,
        non_production_penalty_floor=0.0,
        non_production_penalty_cap=1.0,
    )
    components = ScoreComponents(
        quality=0.8,
        novelty=0.7,
        feasibility=0.6,
        criteria=0.5,
        similarity_penalty=0.9,
        too_safe_penalty=0.7,
        non_production_penalty=0.0,
    )

    checkpoint_id = "checkpoint:replay-a"
    session.add(
        CheckpointSnapshot(
            run_id=run.id,
            checkpoint_id=checkpoint_id,
            captured_at=datetime(2026, 2, 28, 0, 5, tzinfo=UTC),
            active_weights=asdict(weights),
            active_policies={"score_component_bounds": asdict(bounds)},
        )
    )
    payload = {
        "components": asdict(components),
        "weights": asdict(weights),
    }
    session.add(
        ScoreEvent(
            submission_id=submission.id,
            checkpoint_id=checkpoint_id,
            quality_score=components.quality,
            novelty_score=components.novelty,
            feasibility_score=components.feasibility,
            criteria_score=components.criteria,
            final_score=0.123,
            payload=payload,
            payload_checksum=compute_score_event_payload_checksum(payload),
        )
    )
    await session.commit()

    response = await replay_run_scoring(
        run.id,
        payload=ScoringReplayRequest(checkpoint_id=checkpoint_id),
        session=session,
    )

    expected = compose_final_score(components, weights, bounds=bounds)
    assert response.checkpoint_id == checkpoint_id
    assert len(response.submissions) == 1
    assert response.submissions[0].submission_id == submission.id
    assert response.submissions[0].original_final_score == pytest.approx(0.123, abs=1e-6)
    assert response.submissions[0].replay_final_score == pytest.approx(expected.final_score, abs=1e-6)


@pytest.mark.asyncio
async def test_replay_endpoint_uses_latest_snapshot_when_checkpoint_unspecified(session: AsyncSession) -> None:
    run, submission = await _seed_run_submission(session)
    base_components = ScoreComponents(
        quality=0.7,
        novelty=0.7,
        feasibility=0.7,
        criteria=0.7,
        similarity_penalty=0.0,
        too_safe_penalty=0.0,
        non_production_penalty=0.0,
    )
    payload = {
        "components": asdict(base_components),
        "weights": asdict(ActiveWeightsSnapshot(0.35, 0.25, 0.2, 0.2, 0.2, 0.2, 1.0)),
    }

    session.add_all(
        [
            CheckpointSnapshot(
                run_id=run.id,
                checkpoint_id="checkpoint:old",
                captured_at=datetime(2026, 2, 28, 0, 5, tzinfo=UTC),
                active_weights=asdict(ActiveWeightsSnapshot(0.35, 0.25, 0.2, 0.2, 0.2, 0.2, 1.0)),
                active_policies={},
            ),
            CheckpointSnapshot(
                run_id=run.id,
                checkpoint_id="checkpoint:new",
                captured_at=datetime(2026, 2, 28, 0, 6, tzinfo=UTC),
                active_weights=asdict(ActiveWeightsSnapshot(0.5, 0.2, 0.2, 0.1, 0.2, 0.2, 1.0)),
                active_policies={},
            ),
            ScoreEvent(
                submission_id=submission.id,
                checkpoint_id="checkpoint:old",
                quality_score=0.7,
                novelty_score=0.7,
                feasibility_score=0.7,
                criteria_score=0.7,
                final_score=0.1,
                payload=payload,
                payload_checksum=compute_score_event_payload_checksum(payload),
            ),
            ScoreEvent(
                submission_id=submission.id,
                checkpoint_id="checkpoint:new",
                quality_score=0.7,
                novelty_score=0.7,
                feasibility_score=0.7,
                criteria_score=0.7,
                final_score=0.2,
                payload=payload,
                payload_checksum=compute_score_event_payload_checksum(payload),
            ),
        ]
    )
    await session.commit()

    response = await replay_run_scoring(
        run.id,
        payload=ScoringReplayRequest(checkpoint_id=None),
        session=session,
    )

    assert response.checkpoint_id == "checkpoint:new"
    assert len(response.submissions) == 1


@pytest.mark.asyncio
async def test_replay_endpoint_returns_404_when_snapshot_missing(session: AsyncSession) -> None:
    run, _ = await _seed_run_submission(session)
    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await replay_run_scoring(
            run.id,
            payload=ScoringReplayRequest(checkpoint_id="checkpoint:none"),
            session=session,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_replay_endpoint_is_deterministic_with_fixed_replay_seed(session: AsyncSession) -> None:
    run, submission_a = await _seed_run_submission(session)
    replay_seed = derive_run_replay_seed(run.id)
    run.config_snapshot = {
        **run.config_snapshot,
        "reproducibility": {
            "seed_algorithm": REPLAY_SEED_ALGORITHM,
            "run_seed": replay_seed,
        },
    }
    await session.flush()

    agent_b = Agent(run_id=run.id, role=AgentRole.HACKER, name="replay-agent-b")
    session.add(agent_b)
    await session.flush()
    submission_b = Submission(
        run_id=run.id,
        agent_id=agent_b.id,
        state=SubmissionState.PENDING,
        value_hypothesis="Second replay submission for deterministic ordering.",
        summary="Submission B for deterministic replay.",
    )
    session.add(submission_b)
    await session.flush()

    checkpoint_id = "checkpoint:deterministic-seed"
    session.add(
        CheckpointSnapshot(
            run_id=run.id,
            checkpoint_id=checkpoint_id,
            captured_at=datetime(2026, 2, 28, 0, 10, tzinfo=UTC),
            active_weights=asdict(ActiveWeightsSnapshot(0.4, 0.3, 0.2, 0.1, 0.2, 0.2, 1.0)),
            active_policies={},
        )
    )

    components = ScoreComponents(
        quality=0.7,
        novelty=0.6,
        feasibility=0.5,
        criteria=0.4,
        similarity_penalty=0.1,
        too_safe_penalty=0.05,
        non_production_penalty=0.0,
    )
    payload = {
        "components": asdict(components),
        "weights": asdict(ActiveWeightsSnapshot(0.4, 0.3, 0.2, 0.1, 0.2, 0.2, 1.0)),
    }
    session.add_all(
        [
            ScoreEvent(
                submission_id=submission_a.id,
                checkpoint_id=checkpoint_id,
                quality_score=components.quality,
                novelty_score=components.novelty,
                feasibility_score=components.feasibility,
                criteria_score=components.criteria,
                final_score=0.55,
                payload=payload,
                payload_checksum=compute_score_event_payload_checksum(payload),
            ),
            ScoreEvent(
                submission_id=submission_b.id,
                checkpoint_id=checkpoint_id,
                quality_score=components.quality,
                novelty_score=components.novelty,
                feasibility_score=components.feasibility,
                criteria_score=components.criteria,
                final_score=0.55,
                payload=payload,
                payload_checksum=compute_score_event_payload_checksum(payload),
            ),
        ]
    )
    await session.commit()

    first = await replay_run_scoring(
        run.id,
        payload=ScoringReplayRequest(checkpoint_id=checkpoint_id),
        session=session,
    )
    second = await replay_run_scoring(
        run.id,
        payload=ScoringReplayRequest(checkpoint_id=checkpoint_id),
        session=session,
    )

    assert first.model_dump() == second.model_dump()
    assert first.config_snapshot["reproducibility"]["run_seed"] == replay_seed
    assert first.config_snapshot["reproducibility"]["seed_algorithm"] == REPLAY_SEED_ALGORITHM
