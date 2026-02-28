from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.models import Run, ScoreEvent, ScoringWeightConfig, Submission, SubagentEdge

router = APIRouter(prefix="/runs", tags=["run"])


class TimelineEvent(BaseModel):
    event_type: str
    occurred_at: datetime
    entity_id: str
    payload: dict[str, object]


class RunTimelineResponse(BaseModel):
    run_id: uuid.UUID
    events: list[TimelineEvent]


@router.get("/{run_id}/timeline", response_model=RunTimelineResponse)
async def get_run_timeline(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RunTimelineResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    events: list[TimelineEvent] = []

    spawn_stmt: Select[tuple[SubagentEdge]] = select(SubagentEdge).where(SubagentEdge.run_id == run_id)
    spawn_edges = (await session.execute(spawn_stmt)).scalars().all()
    for edge in spawn_edges:
        events.append(
            TimelineEvent(
                event_type="spawn",
                occurred_at=edge.created_at,
                entity_id=str(edge.id),
                payload={
                    "parent_agent_id": str(edge.parent_agent_id),
                    "child_agent_id": str(edge.child_agent_id),
                    "depth": edge.depth,
                },
            )
        )

    submit_stmt: Select[tuple[Submission]] = select(Submission).where(Submission.run_id == run_id)
    submissions = (await session.execute(submit_stmt)).scalars().all()
    for submission in submissions:
        events.append(
            TimelineEvent(
                event_type="submit",
                occurred_at=submission.created_at,
                entity_id=str(submission.id),
                payload={"agent_id": str(submission.agent_id), "state": str(submission.state)},
            )
        )

    score_stmt: Select[tuple[ScoreEvent]] = (
        select(ScoreEvent).join(Submission, ScoreEvent.submission_id == Submission.id).where(Submission.run_id == run_id)
    )
    score_events = (await session.execute(score_stmt)).scalars().all()
    for score_event in score_events:
        events.append(
            TimelineEvent(
                event_type="score",
                occurred_at=score_event.created_at,
                entity_id=str(score_event.id),
                payload={
                    "submission_id": str(score_event.submission_id),
                    "checkpoint_id": score_event.checkpoint_id,
                    "final_score": score_event.final_score,
                },
            )
        )

    weight_stmt: Select[tuple[ScoringWeightConfig]] = select(ScoringWeightConfig).where(ScoringWeightConfig.run_id == run_id)
    weight_configs = (await session.execute(weight_stmt)).scalars().all()
    for weight_config in weight_configs:
        events.append(
            TimelineEvent(
                event_type="weight-change",
                occurred_at=weight_config.effective_from,
                entity_id=str(weight_config.id),
                payload={"weights": weight_config.weights},
            )
        )

    events.sort(key=lambda event: (event.occurred_at, event.event_type, event.entity_id))
    return RunTimelineResponse(run_id=run_id, events=events)
