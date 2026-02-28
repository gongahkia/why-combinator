from __future__ import annotations

import statistics
import uuid
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.diversity import compute_run_diversity_index
from app.db.enums import SubmissionState
from app.db.models import Agent, Run, Submission


async def compute_run_metrics(session: AsyncSession, run_id: uuid.UUID) -> dict[str, float]:
    run = await session.get(Run, run_id)
    if run is None:
        raise ValueError("run not found")

    accepted_stmt: Select[tuple[Submission]] = select(Submission).where(
        Submission.run_id == run_id,
        Submission.state == SubmissionState.ACCEPTED,
        Submission.accepted_at.is_not(None),
    )
    accepted_submissions = (await session.execute(accepted_stmt)).scalars().all()
    accepted_mvp_count = len(accepted_submissions)

    first_accept_by_agent: dict[uuid.UUID, datetime] = {}
    for submission in accepted_submissions:
        if submission.accepted_at is None:
            continue
        previous = first_accept_by_agent.get(submission.agent_id)
        if previous is None or submission.accepted_at < previous:
            first_accept_by_agent[submission.agent_id] = submission.accepted_at

    median_time_to_first_accepted = 0.0
    if run.started_at is not None and first_accept_by_agent:
        durations = [
            max(0.0, (accepted_at - run.started_at).total_seconds())
            for accepted_at in first_accept_by_agent.values()
        ]
        median_time_to_first_accepted = float(statistics.median(durations))

    total_agents_stmt: Select[tuple[int]] = select(func.count()).select_from(Agent).where(Agent.run_id == run_id)
    total_agents = (await session.execute(total_agents_stmt)).scalar_one()
    producer_share = (len(first_accept_by_agent) / total_agents) if total_agents > 0 else 0.0

    diversity_index = await compute_run_diversity_index(session, run_id)
    return {
        "accepted_mvp_count": float(accepted_mvp_count),
        "median_time_to_first_accepted_mvp": round(median_time_to_first_accepted, 6),
        "diversity_index": diversity_index,
        "producer_share": round(producer_share, 6),
    }


async def emit_run_metrics(
    session: AsyncSession,
    run_id: uuid.UUID,
    redis_client: Redis | None = None,
) -> dict[str, float]:
    metrics = await compute_run_metrics(session, run_id)
    if redis_client is not None:
        await redis_client.publish(
            "run_metrics",
            str(
                {
                    "run_id": str(run_id),
                    **metrics,
                }
            ),
        )
    return metrics
