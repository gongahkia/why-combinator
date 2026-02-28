from __future__ import annotations

from celery import shared_task

from app.orchestrator.jobs import run_checkpoint_score_job, run_hacker_job, run_judge_job
from app.queue.budget import create_redis_client, reserve_budget, task_cost_from_env


def _with_budget_guard(run_id: str, task_name: str, default_cost: int) -> tuple[bool, dict[str, str]]:
    redis_client = create_redis_client()
    try:
        accepted, remaining = reserve_budget(redis_client, run_id, task_cost_from_env(task_name, default_cost))
    finally:
        redis_client.close()
    if not accepted:
        return False, {
            "job_type": task_name,
            "run_id": run_id,
            "status": "budget_exhausted",
            "budget_remaining": "unknown" if remaining is None else str(remaining),
        }
    return True, {}


@shared_task(name="app.queue.jobs.hacker_run", bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def hacker_run(self, run_id: str) -> dict[str, str]:
    accepted, payload = _with_budget_guard(run_id, "hacker-run", default_cost=10)
    if not accepted:
        return payload
    return run_hacker_job(run_id)


@shared_task(name="app.queue.jobs.judge_run", bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def judge_run(self, run_id: str) -> dict[str, str]:
    accepted, payload = _with_budget_guard(run_id, "judge-run", default_cost=5)
    if not accepted:
        return payload
    return run_judge_job(run_id)


@shared_task(
    name="app.queue.jobs.checkpoint_score",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def checkpoint_score(self, run_id: str) -> dict[str, str]:
    accepted, payload = _with_budget_guard(run_id, "checkpoint-score", default_cost=2)
    if not accepted:
        return payload
    return run_checkpoint_score_job(run_id)
