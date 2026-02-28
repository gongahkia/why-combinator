from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.config import load_settings
from app.db.enums import SubmissionState
from app.db.models import Agent, Challenge, JudgeProfile, JudgeScore, PenaltyEvent, Run, Submission
from app.integrations.why_combinator_bridge import (
    WhyCombinatorSimulationRequest,
    WhyCombinatorSimulationResult,
    WhyCombinatorUnavailableError,
    infer_startup_industry,
    map_challenge_to_why_parameters,
    run_why_combinator_market_simulation,
)
from app.scoring.replay import (
    ReplayNotFoundError,
    ReplayValidationError,
    generate_replay_score_deltas,
    replay_scoring_from_frozen_snapshot,
)

router = APIRouter(prefix="/runs", tags=["analytics"])


class AgentProductivityMetrics(BaseModel):
    agent_id: uuid.UUID
    agent_name: str
    attempts: int
    accepted_mvps: int
    penalties: int
    penalty_total: float


class AgentProductivityResponse(BaseModel):
    run_id: uuid.UUID
    metrics: list[AgentProductivityMetrics]


class JudgeDisagreementMetrics(BaseModel):
    judge_profile_id: uuid.UUID
    domain: str
    scored_items: int
    mean_absolute_disagreement: float
    max_absolute_disagreement: float


class CheckpointVarianceMetrics(BaseModel):
    checkpoint_id: str
    scored_items: int
    inter_judge_variance: float


class JudgeDisagreementResponse(BaseModel):
    run_id: uuid.UUID
    judge_metrics: list[JudgeDisagreementMetrics]
    checkpoint_variance: list[CheckpointVarianceMetrics]


class ReplayDiffSubmissionMetrics(BaseModel):
    submission_id: uuid.UUID
    original_final_score: float
    replay_final_score: float
    delta: float
    absolute_delta: float
    original_rank: int
    replay_rank: int
    rank_shift: int
    direction: str


class ReplayDiffResponse(BaseModel):
    run_id: uuid.UUID
    checkpoint_id: str
    submissions: list[ReplayDiffSubmissionMetrics]


class MarketSimulationRequest(BaseModel):
    industry: str | None = Field(default=None, min_length=2, max_length=64)
    stage: Literal["idea", "mvp", "launch", "growth", "scale", "exit"] = "mvp"
    duration_ticks: int = Field(default=60, ge=10, le=600)
    model: str = Field(default="mock", min_length=2, max_length=64)
    speed_multiplier: float = Field(default=250.0, gt=0.0, le=5000.0)
    persist_simulation: bool = False


class MarketSimulationResponse(BaseModel):
    run_id: uuid.UUID
    simulation_id: str
    industry: str
    stage: str
    seed: int | None
    integration_mode: str
    overlap_highlights: list[str]
    latest_metrics: dict[str, float]
    recommendation: str
    strengths: list[str]
    weaknesses: list[str]


@router.get("/{run_id}/analytics/agents/productivity", response_model=AgentProductivityResponse)
async def get_agent_productivity_metrics(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AgentProductivityResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    agent_stmt: Select[tuple[Agent]] = select(Agent).where(Agent.run_id == run_id).order_by(Agent.created_at.asc(), Agent.id.asc())
    agents = (await session.execute(agent_stmt)).scalars().all()

    attempts_stmt: Select[tuple[uuid.UUID, int, int]] = (
        select(
            Submission.agent_id,
            func.count(Submission.id),
            func.sum(case((Submission.state == SubmissionState.ACCEPTED, 1), else_=0)),
        )
        .where(Submission.run_id == run_id)
        .group_by(Submission.agent_id)
    )
    attempt_rows = (await session.execute(attempts_stmt)).all()
    attempts_by_agent: dict[uuid.UUID, tuple[int, int]] = {
        row[0]: (int(row[1]), int(row[2] or 0))
        for row in attempt_rows
    }

    penalties_stmt: Select[tuple[uuid.UUID, int, float]] = (
        select(
            Submission.agent_id,
            func.count(PenaltyEvent.id),
            func.coalesce(func.sum(PenaltyEvent.value), 0.0),
        )
        .join(Submission, Submission.id == PenaltyEvent.submission_id)
        .where(Submission.run_id == run_id)
        .group_by(Submission.agent_id)
    )
    penalty_rows = (await session.execute(penalties_stmt)).all()
    penalties_by_agent: dict[uuid.UUID, tuple[int, float]] = {
        row[0]: (int(row[1]), float(row[2]))
        for row in penalty_rows
    }

    metrics = []
    for agent in agents:
        attempts, accepted = attempts_by_agent.get(agent.id, (0, 0))
        penalties, penalty_total = penalties_by_agent.get(agent.id, (0, 0.0))
        metrics.append(
            AgentProductivityMetrics(
                agent_id=agent.id,
                agent_name=agent.name,
                attempts=attempts,
                accepted_mvps=accepted,
                penalties=penalties,
                penalty_total=round(penalty_total, 6),
            )
        )

    metrics.sort(key=lambda item: (-item.accepted_mvps, -item.attempts, item.penalty_total, str(item.agent_id)))
    return AgentProductivityResponse(run_id=run_id, metrics=metrics)


@router.get("/{run_id}/analytics/judges/disagreement", response_model=JudgeDisagreementResponse)
async def get_judge_disagreement_metrics(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> JudgeDisagreementResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    profile_stmt: Select[tuple[JudgeProfile]] = select(JudgeProfile).where(JudgeProfile.challenge_id == run.challenge_id)
    judge_profiles = (await session.execute(profile_stmt)).scalars().all()

    score_stmt: Select[tuple[JudgeScore]] = (
        select(JudgeScore)
        .options(selectinload(JudgeScore.judge_profile))
        .join(Submission, Submission.id == JudgeScore.submission_id)
        .where(Submission.run_id == run_id)
    )
    judge_scores = (await session.execute(score_stmt)).scalars().all()

    grouped: dict[tuple[str, uuid.UUID], list[JudgeScore]] = defaultdict(list)
    for row in judge_scores:
        grouped[(row.checkpoint_id, row.submission_id)].append(row)

    judge_disagreements: dict[uuid.UUID, list[float]] = defaultdict(list)
    checkpoint_variances: dict[str, list[float]] = defaultdict(list)
    for (checkpoint_id, _submission_id), rows in grouped.items():
        values = [float(row.score) for row in rows]
        if not values:
            continue
        mean_score = sum(values) / len(values)
        variance = sum((value - mean_score) ** 2 for value in values) / len(values)
        checkpoint_variances[checkpoint_id].append(variance)
        for row in rows:
            judge_disagreements[row.judge_profile_id].append(abs(float(row.score) - mean_score))

    judge_metrics: list[JudgeDisagreementMetrics] = []
    for profile in judge_profiles:
        disagreements = judge_disagreements.get(profile.id, [])
        if disagreements:
            mean_abs = sum(disagreements) / len(disagreements)
            max_abs = max(disagreements)
        else:
            mean_abs = 0.0
            max_abs = 0.0
        judge_metrics.append(
            JudgeDisagreementMetrics(
                judge_profile_id=profile.id,
                domain=profile.domain,
                scored_items=len(disagreements),
                mean_absolute_disagreement=round(mean_abs, 6),
                max_absolute_disagreement=round(max_abs, 6),
            )
        )

    checkpoint_metrics = [
        CheckpointVarianceMetrics(
            checkpoint_id=checkpoint_id,
            scored_items=len(variances),
            inter_judge_variance=round(sum(variances) / len(variances), 6) if variances else 0.0,
        )
        for checkpoint_id, variances in sorted(checkpoint_variances.items())
    ]
    judge_metrics.sort(key=lambda item: item.domain.lower())
    return JudgeDisagreementResponse(
        run_id=run_id,
        judge_metrics=judge_metrics,
        checkpoint_variance=checkpoint_metrics,
    )


@router.get("/{run_id}/analytics/replay/diff", response_model=ReplayDiffResponse)
async def get_replay_diff_metrics(
    run_id: uuid.UUID,
    checkpoint_id: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> ReplayDiffResponse:
    try:
        replay = await replay_scoring_from_frozen_snapshot(
            session,
            run_id=run_id,
            checkpoint_id=checkpoint_id,
        )
    except ReplayNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReplayValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    diffs = generate_replay_score_deltas(replay)
    return ReplayDiffResponse(
        run_id=run_id,
        checkpoint_id=replay.checkpoint_id,
        submissions=[
            ReplayDiffSubmissionMetrics(
                submission_id=row.submission_id,
                original_final_score=row.original_final_score,
                replay_final_score=row.replay_final_score,
                delta=row.delta,
                absolute_delta=row.absolute_delta,
                original_rank=row.original_rank,
                replay_rank=row.replay_rank,
                rank_shift=row.rank_shift,
                direction=row.direction,
            )
            for row in diffs
        ],
    )


@router.post("/{run_id}/analytics/market-simulation", response_model=MarketSimulationResponse)
async def get_market_simulation_metrics(
    run_id: uuid.UUID,
    payload: MarketSimulationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MarketSimulationResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    challenge = await session.get(Challenge, run.challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")

    settings = load_settings()
    industry = payload.industry.strip().lower() if payload.industry else infer_startup_industry(challenge.prompt)
    seed = _extract_run_seed(run)
    simulation_request = WhyCombinatorSimulationRequest(
        simulation_name=f"{challenge.title} :: run {str(run.id)[:8]}",
        industry=industry,
        description=challenge.prompt,
        stage=payload.stage,
        duration_ticks=payload.duration_ticks,
        model=payload.model,
        speed_multiplier=payload.speed_multiplier,
        seed=seed,
        parameters=map_challenge_to_why_parameters(
            complexity_slider=challenge.complexity_slider,
            minimum_quality_threshold=challenge.minimum_quality_threshold,
            risk_appetite=challenge.risk_appetite,
            iteration_window_seconds=challenge.iteration_window_seconds,
        ),
        persist_simulation=payload.persist_simulation,
        repo_path=settings.why_combinator_repo_path,
        data_dir=settings.why_combinator_data_dir,
    )

    try:
        simulation = await asyncio.to_thread(
            run_why_combinator_market_simulation,
            simulation_request,
        )
    except WhyCombinatorUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return _to_market_simulation_response(
        run_id=run.id,
        industry=industry,
        stage=payload.stage,
        seed=seed,
        simulation=simulation,
    )


def _extract_run_seed(run: Run) -> int | None:
    reproducibility = run.config_snapshot.get("reproducibility")
    if not isinstance(reproducibility, dict):
        return None
    run_seed = reproducibility.get("run_seed")
    if isinstance(run_seed, int):
        return run_seed
    return None


def _to_market_simulation_response(
    *,
    run_id: uuid.UUID,
    industry: str,
    stage: str,
    seed: int | None,
    simulation: WhyCombinatorSimulationResult,
) -> MarketSimulationResponse:
    summary = simulation.summary
    recommendation = summary.get("recommendation")
    strengths = _coerce_string_list(summary.get("strengths"))
    weaknesses = _coerce_string_list(summary.get("weaknesses"))

    return MarketSimulationResponse(
        run_id=run_id,
        simulation_id=simulation.simulation_id,
        industry=industry,
        stage=stage,
        seed=seed,
        integration_mode="hackathon-runtime + why-combinator market simulation",
        overlap_highlights=[
            "Both systems use deterministic seeds for replay-safe experiments.",
            "Both use multi-agent orchestration with phase/state progression.",
            "Hackathon quality scoring is augmented with market and runway stress metrics.",
        ],
        latest_metrics=simulation.latest_metrics,
        recommendation=recommendation if isinstance(recommendation, str) else "no recommendation",
        strengths=strengths,
        weaknesses=weaknesses,
    )


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []
