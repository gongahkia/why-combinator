from __future__ import annotations

import asyncio
import json
import os
import shlex
import uuid
from dataclasses import asdict, dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import load_settings
from app.judging.worker import run_judge_scoring_worker
from app.orchestrator.run_completion import complete_run
from app.orchestrator.subagent_quota import check_and_reserve_subagent_quota
from app.queue.budget import create_redis_client
from app.sandbox.runner import HackerAgentRunSpec, HackerAgentRunner, load_hacker_runner_limits_from_env
from app.scoring.checkpoint import run_checkpoint_scoring_worker
from app.security.secrets import build_scoped_model_secret_env
from app.validation.model_schema import ModelResponseValidationError, validate_hacker_response_json


@dataclass
class JobResult:
    job_type: str
    run_id: str
    status: str

def run_hacker_job(run_id: str, trace_id: str | None = None) -> dict[str, str]:
    if os.getenv("HACKER_RUNNER_ENABLED", "false").lower() != "true":
        return asdict(JobResult(job_type="hacker-run", run_id=run_id, status="runner-disabled"))

    image = os.getenv("HACKER_RUNNER_IMAGE", "alpine:3.20")
    hacker_output_payload = json.dumps(
        {
            "summary": f"Run {run_id} MVP summary output",
            "value_hypothesis": "This MVP should improve challenge KPI throughput.",
            "artifacts": ["mvp_bundle.zip"],
        }
    )
    command = [
        "sh",
        "-lc",
        f"printf '%s' {shlex.quote(hacker_output_payload)}",
    ]
    runner = HackerAgentRunner()
    scoped_env = build_scoped_model_secret_env(
        base_env={"RUN_ID": run_id, "TRACE_ID": trace_id or ""},
        ttl_seconds=int(os.getenv("MODEL_API_KEY_TTL_SECONDS", "300")),
    )
    result = runner.run(
        spec=HackerAgentRunSpec(
            agent_id=run_id,
            image=image,
            command=command,
            env=scoped_env,
            task_type="hacker_run",
            trace_id=trace_id or "",
        ),
        limits=load_hacker_runner_limits_from_env(),
    )
    hacker_schema_valid = "false"
    hacker_schema_error = ""
    try:
        validate_hacker_response_json(result.stdout.strip())
        hacker_schema_valid = "true"
    except ModelResponseValidationError as exc:
        hacker_schema_error = str(exc)

    return {
        "job_type": "hacker-run",
        "run_id": run_id,
        "status": "startup_timeout" if result.startup_timed_out else ("timeout" if result.timed_out else "completed"),
        "container_name": result.container_name,
        "exit_code": "" if result.exit_code is None else str(result.exit_code),
        "log_path": result.log_path or "",
        "trace_id": trace_id or "",
        "hacker_schema_valid": hacker_schema_valid,
        "hacker_schema_error": hacker_schema_error,
    }



def run_judge_job(run_id: str, trace_id: str | None = None) -> dict[str, str]:
    async def _run() -> int:
        settings = load_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            created = await run_judge_scoring_worker(session, uuid.UUID(run_id), trace_id=trace_id)
        await engine.dispose()
        return created

    created_scores = asyncio.run(_run())
    return {
        "job_type": "judge-run",
        "run_id": run_id,
        "status": "completed",
        "created_scores": str(created_scores),
        "trace_id": trace_id or "",
    }



def run_checkpoint_score_job(run_id: str, trace_id: str | None = None) -> dict[str, str]:
    async def _run() -> dict[str, str]:
        settings = load_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            result = await run_checkpoint_scoring_worker(session, uuid.UUID(run_id), trace_id=trace_id)
        await engine.dispose()
        return {
            "checkpoint_id": result.checkpoint_id,
            "scored_submissions": str(result.scored_submissions),
            "skipped_submissions": str(result.skipped_submissions),
            "judge_scores_created": str(result.judge_scores_created),
            "leaderboard_entries": str(result.leaderboard_entries),
        }

    details = asyncio.run(_run())
    return {
        "job_type": "checkpoint-score",
        "run_id": run_id,
        "status": "completed",
        "trace_id": trace_id or "",
        **details,
    }


def run_complete_run_job(run_id: str, trace_id: str | None = None) -> dict[str, str]:
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
        "auto_attempts_created": str(result["auto_attempts_created"]),
        "finalized_submissions": str(result["finalized_submissions"]),
        "non_production_penalties": str(result["non_production_penalties"]),
        "leaderboard_entries": str(result["leaderboard_entries"]),
        "trace_id": trace_id or "",
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
