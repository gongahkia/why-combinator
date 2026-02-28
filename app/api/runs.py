from __future__ import annotations

import uuid
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.db.enums import RunState
from app.db.models import Challenge, JudgeProfile, Run
from app.orchestrator.baseline import run_baseline_idea_generator_job
from app.orchestrator.run_validation import RunStartValidationError, validate_domain_expert_judge_present

router = APIRouter(prefix="/challenges", tags=["runs"])


class RunResponse(BaseModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    state: RunState
    started_at: datetime | None
    ended_at: datetime | None
    config_snapshot: dict[str, object]
    created_at: datetime
    updated_at: datetime


@router.post(
    "/{challenge_id}/runs/start",
    status_code=status.HTTP_201_CREATED,
    response_model=RunResponse,
)
async def start_run(
    challenge_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    challenge = await session.get(Challenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="challenge not found")

    try:
        await validate_domain_expert_judge_present(session, challenge_id)
    except RunStartValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    judge_stmt: Select[tuple[JudgeProfile]] = select(JudgeProfile).where(JudgeProfile.challenge_id == challenge_id)
    judge_profiles = (await session.execute(judge_stmt)).scalars().all()
    config_snapshot = {
        "challenge": {
            "id": str(challenge.id),
            "title": challenge.title,
            "prompt": challenge.prompt,
            "iteration_window_seconds": challenge.iteration_window_seconds,
            "minimum_quality_threshold": challenge.minimum_quality_threshold,
            "risk_appetite": challenge.risk_appetite,
            "complexity_slider": challenge.complexity_slider,
        },
        "judge_profiles": [
            {
                "id": str(profile.id),
                "domain": profile.domain,
                "scoring_style": profile.scoring_style,
                "profile_prompt": profile.profile_prompt,
                "head_judge": profile.head_judge,
                "source_type": profile.source_type,
            }
            for profile in judge_profiles
        ],
    }
    started_at = datetime.now(timezone.utc)
    run = Run(
        challenge_id=challenge_id,
        state=RunState.RUNNING,
        started_at=started_at,
        config_snapshot=config_snapshot,
    )
    session.add(run)
    await session.flush()
    baseline_rows = await run_baseline_idea_generator_job(session, run, challenge)
    await session.commit()
    await session.refresh(run)
    budget_key = f"run:{run.id}:budget_remaining"
    await request.app.state.redis.setnx(budget_key, request.app.state.settings.default_run_budget_units)

    event = {
        "event_type": "run_started",
        "occurred_at": started_at.isoformat(),
        "run_id": str(run.id),
        "challenge_id": str(challenge_id),
        "config_snapshot": config_snapshot,
        "baseline_vector_count": len(baseline_rows),
        "budget_key": budget_key,
    }
    await request.app.state.redis.publish("run_events", json.dumps(event))

    return RunResponse.model_validate(run, from_attributes=True)
