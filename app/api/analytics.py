from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.enums import SubmissionState
from app.db.models import Agent, PenaltyEvent, Run, Submission

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
