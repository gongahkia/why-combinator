from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import asdict, dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import load_settings
from app.judging.worker import run_judge_scoring_worker
from app.orchestrator.run_completion import complete_run
from app.orchestrator.subagent_quota import check_and_reserve_subagent_quota
from app.queue.budget import create_redis_client
from app.sandbox.runner import HackerAgentRunSpec, HackerAgentRunner, load_hacker_runner_limits_from_env


@dataclass
class JobResult:
    job_type: str
    run_id: str
    status: str



def run_hacker_job(run_id: str) -> dict[str, str]:
    if os.getenv("HACKER_RUNNER_ENABLED", "false").lower() != "true":
        return asdict(JobResult(job_type="hacker-run", run_id=run_id, status="runner-disabled"))

    image = os.getenv("HACKER_RUNNER_IMAGE", "alpine:3.20")
    command = [
        "sh",
        "-lc",
        f"echo running_hacker_agent_for_run={run_id}",
    ]
    runner = HackerAgentRunner()
    result = runner.run(
        spec=HackerAgentRunSpec(
            agent_id=run_id,
            image=image,
            command=command,
            env={"RUN_ID": run_id},
        ),
        limits=load_hacker_runner_limits_from_env(),
    )
    return {
        "job_type": "hacker-run",
        "run_id": run_id,
        "status": "timeout" if result.timed_out else "completed",
        "container_name": result.container_name,
        "exit_code": "" if result.exit_code is None else str(result.exit_code),
    }



def run_judge_job(run_id: str) -> dict[str, str]:
    async def _run() -> int:
        settings = load_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            created = await run_judge_scoring_worker(session, uuid.UUID(run_id))
        await engine.dispose()
        return created

    created_scores = asyncio.run(_run())
    return {
        "job_type": "judge-run",
        "run_id": run_id,
        "status": "completed",
        "created_scores": str(created_scores),
    }



def run_checkpoint_score_job(run_id: str) -> dict[str, str]:
    return asdict(JobResult(job_type="checkpoint-score", run_id=run_id, status="queued"))


def run_complete_run_job(run_id: str) -> dict[str, str]:
    async def _run() -> dict[str, int]:
        settings = load_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            result = await complete_run(session, uuid.UUID(run_id))
        await engine.dispose()
        return result

    result = asyncio.run(_run())
    return {
        "job_type": "run-complete",
        "run_id": run_id,
        "status": "completed",
        "finalized_submissions": str(result["finalized_submissions"]),
        "non_production_penalties": str(result["non_production_penalties"]),
        "leaderboard_entries": str(result["leaderboard_entries"]),
    }


def reserve_subagent_spawn_quota(run_id: str, parent_agent_id: str) -> dict[str, str]:
    redis_client = create_redis_client()
    try:
        accepted, remaining = check_and_reserve_subagent_quota(redis_client, run_id, parent_agent_id)
    finally:
        redis_client.close()
    return {
        "job_type": "subagent-spawn",
        "run_id": run_id,
        "parent_agent_id": parent_agent_id,
        "status": "accepted" if accepted else "quota_exhausted",
        "spawn_quota_remaining": str(remaining),
    }
