from __future__ import annotations

import asyncio
import json
import os
import shlex
import uuid
from dataclasses import asdict, dataclass

import redis.asyncio as redis_async
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import load_settings
from app.events.outbox import relay_outbox_events
from app.judging.worker import run_judge_scoring_worker
from app.orchestrator.reproducibility import derive_agent_prompt_seed, derive_run_replay_seed
from app.orchestrator.run_completion import complete_run
from app.orchestrator.subagent_quota import check_and_reserve_subagent_quota
from app.prompting.hacker import HackerPromptInput, render_hacker_agent_prompt
from app.queue.budget import create_redis_client
from app.sandbox.runner import HackerAgentRunSpec, HackerAgentRunner, load_hacker_runner_limits_from_env
from app.sandbox.cleanup import cleanup_sandbox_resources
from app.scoring.weights import DEFAULT_WEIGHTS
from app.scheduler.run_timeout import fail_stale_runs_without_worker_heartbeat
from app.scoring.checkpoint import run_checkpoint_scoring_worker
from app.security.secrets import build_scoped_model_secret_env
from app.validation.model_schema import ModelResponseValidationError, validate_hacker_response_json


@dataclass
class JobResult:
    job_type: str
    run_id: str
    status: str


def _default_hacker_prompt_input(run_id: str, run_seed: int, agent_seed: int, agent_label: str) -> HackerPromptInput:
    return HackerPromptInput(
        challenge_title=f"Run {run_id}",
        challenge_prompt="Build an MVP attempt that improves a measurable business KPI.",
        criteria={
            "quality": DEFAULT_WEIGHTS.quality,
            "novelty": DEFAULT_WEIGHTS.novelty,
            "feasibility": DEFAULT_WEIGHTS.feasibility,
            "criteria": DEFAULT_WEIGHTS.criteria,
        },
        risk_appetite="balanced",
        complexity_slider=0.5,
        run_seed=run_seed,
        agent_seed=agent_seed,
        agent_label=agent_label,
    )


def run_hacker_job(
    run_id: str,
    trace_id: str | None = None,
    agent_id: str | None = None,
    run_seed: int | None = None,
) -> dict[str, str]:
    effective_agent_id = agent_id or run_id
    effective_run_seed = derive_run_replay_seed(run_id) if run_seed is None else int(run_seed)
    effective_agent_seed = derive_agent_prompt_seed(effective_run_seed, effective_agent_id)
    prompt_input = _default_hacker_prompt_input(
        run_id=run_id,
        run_seed=effective_run_seed,
        agent_seed=effective_agent_seed,
        agent_label=effective_agent_id,
    )
    prompt_text = render_hacker_agent_prompt(prompt_input)
    if os.getenv("HACKER_RUNNER_ENABLED", "false").lower() != "true":
        return {
            **asdict(JobResult(job_type="hacker-run", run_id=run_id, status="runner-disabled")),
            "trace_id": trace_id or "",
            "agent_id": effective_agent_id,
            "run_seed": str(effective_run_seed),
            "agent_seed": str(effective_agent_seed),
        }

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
        base_env={
            "RUN_ID": run_id,
            "TRACE_ID": trace_id or "",
            "AGENT_ID": effective_agent_id,
            "REPLAY_RUN_SEED": str(effective_run_seed),
            "REPLAY_AGENT_SEED": str(effective_agent_seed),
            "HACKER_AGENT_PROMPT": prompt_text,
        },
        ttl_seconds=int(os.getenv("MODEL_API_KEY_TTL_SECONDS", "300")),
    )
    result = runner.run(
        spec=HackerAgentRunSpec(
            agent_id=effective_agent_id,
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
        "agent_id": effective_agent_id,
        "run_seed": str(effective_run_seed),
        "agent_seed": str(effective_agent_seed),
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


def run_outbox_relay_job(trace_id: str | None = None, batch_size: int | None = None) -> dict[str, str]:
    async def _run() -> dict[str, str]:
        settings = load_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        redis_client = create_redis_client()
        try:
            async with session_factory() as session:
                result = await relay_outbox_events(session, redis_client, batch_size=batch_size)
                await session.commit()
        finally:
            redis_client.close()
            await engine.dispose()
        return {
            "processed": str(result.processed),
            "published": str(result.published),
            "deduplicated": str(result.deduplicated),
            "failed": str(result.failed),
        }

    details = asyncio.run(_run())
    return {
        "job_type": "outbox-relay",
        "status": "completed",
        "trace_id": trace_id or "",
        **details,
    }


def run_scheduler_heartbeat_monitor_job(trace_id: str | None = None) -> dict[str, str]:
    async def _run() -> dict[str, str]:
        from app.scheduler.heartbeat import monitor_scheduler_heartbeat_and_trigger_failover

        settings = load_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        redis_client = redis_async.from_url(settings.redis_url, decode_responses=True)
        try:
            async with session_factory() as session:
                result = await monitor_scheduler_heartbeat_and_trigger_failover(session, redis_client)
                await session.commit()
        finally:
            await redis_client.aclose()
            await engine.dispose()
        return {
            "failover_triggered": "true" if result.failover_triggered else "false",
            "reason": result.reason,
            "scheduled_runs": str(len(result.scheduled_run_ids)),
        }

    details = asyncio.run(_run())
    return {
        "job_type": "scheduler-heartbeat-monitor",
        "status": "completed",
        "trace_id": trace_id or "",
        **details,
    }


def run_stale_run_heartbeat_watchdog_job(trace_id: str | None = None) -> dict[str, str]:
    async def _run() -> dict[str, str]:
        settings = load_settings()
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        redis_client = redis_async.from_url(settings.redis_url, decode_responses=True)
        try:
            async with session_factory() as session:
                failed_runs = await fail_stale_runs_without_worker_heartbeat(session, redis_client)
        finally:
            await redis_client.aclose()
            await engine.dispose()
        return {
            "failed_runs": str(len(failed_runs)),
        }

    details = asyncio.run(_run())
    return {
        "job_type": "run-heartbeat-watchdog",
        "status": "completed",
        "trace_id": trace_id or "",
        **details,
    }


def run_sandbox_cleanup_job(trace_id: str | None = None) -> dict[str, str]:
    summary = cleanup_sandbox_resources()
    return {
        "job_type": "sandbox-cleanup",
        "status": "completed",
        "trace_id": trace_id or "",
        **summary.as_dict(),
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
