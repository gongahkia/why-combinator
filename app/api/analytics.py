from __future__ import annotations

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.db.enums import SubmissionState
from app.db.models import Agent, JudgeProfile, JudgeScore, PenaltyEvent, Run, Submission

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
