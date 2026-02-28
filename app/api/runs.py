from __future__ import annotations

import uuid
from datetime import datetime, timezone
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.api.errors import BUDGET_EXHAUSTED_ERROR, SANDBOX_FAILURE_ERROR, VALIDATION_ERROR
from app.api.rate_limit import rate_limit_dependency
from app.db.enums import RunState
from app.db.models import Challenge, JudgeProfile, Run
from app.events.bus import emit_run_event, make_run_lifecycle_event
from app.orchestrator.baseline import run_baseline_idea_generator_job
from app.orchestrator.run_validation import RunStartValidationError, validate_domain_expert_judge_present
from app.queue.celery_app import celery_app

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


class RunCancelResponse(BaseModel):
    run_id: uuid.UUID
    state: RunState
    killed_containers: list[str]
    revoked_task_ids: list[str]


@router.post(
    "/{challenge_id}/runs/start",
    status_code=status.HTTP_201_CREATED,
    response_model=RunResponse,
    responses={
        422: VALIDATION_ERROR,
        429: BUDGET_EXHAUSTED_ERROR,
        503: SANDBOX_FAILURE_ERROR,
    },
)
async def start_run(
    challenge_id: uuid.UUID,
    request: Request,
    _rate_limit: None = rate_limit_dependency("run-control", capacity=20, refill_per_second=0.5),
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

    event = make_run_lifecycle_event(
        event_type="run_started",
        run_id=run.id,
        challenge_id=challenge_id,
        payload={
            "config_snapshot": config_snapshot,
            "baseline_vector_count": len(baseline_rows),
            "budget_key": budget_key,
            "started_at": started_at.isoformat(),
        },
    )
    await emit_run_event(request.app.state.redis, event)

    return RunResponse.model_validate(run, from_attributes=True)


def _kill_active_run_containers(run_id: uuid.UUID) -> list[str]:
    run_token = str(run_id)[:12]
    list_proc = subprocess.run(
        ["docker", "ps", "-q", "--filter", f"name=hacker-agent-{run_token}"],
        capture_output=True,
        text=True,
        check=False,
    )
    container_ids = [line.strip() for line in list_proc.stdout.splitlines() if line.strip()]
    for container_id in container_ids:
        subprocess.run(["docker", "kill", container_id], check=False, capture_output=True, text=True)
    return container_ids


def _revoke_run_tasks(run_id: uuid.UUID) -> list[str]:
    revoked: list[str] = []
    run_id_str = str(run_id)
    inspect_client = celery_app.control.inspect()
    for bucket in (inspect_client.active() or {}, inspect_client.reserved() or {}):
        for tasks in bucket.values():
            for task in tasks:
                task_id = task.get("id")
                args_repr = task.get("argsrepr", "")
                if task_id and run_id_str in str(args_repr):
                    celery_app.control.revoke(task_id, terminate=True)
                    revoked.append(task_id)
    return revoked


@router.post("/{challenge_id}/runs/{run_id}/cancel", response_model=RunCancelResponse)
async def cancel_run(
    challenge_id: uuid.UUID,
    run_id: uuid.UUID,
    _rate_limit: None = rate_limit_dependency("run-control", capacity=20, refill_per_second=0.5),
    session: AsyncSession = Depends(get_db_session),
) -> RunCancelResponse:
    run = await session.get(Run, run_id)
    if run is None or run.challenge_id != challenge_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    killed_containers = _kill_active_run_containers(run_id)
    revoked_task_ids = _revoke_run_tasks(run_id)
    run.state = RunState.CANCELED
    run.ended_at = datetime.now(timezone.utc)
    await session.commit()

    return RunCancelResponse(
        run_id=run.id,
        state=run.state,
        killed_containers=killed_containers,
        revoked_task_ids=revoked_task_ids,
    )
