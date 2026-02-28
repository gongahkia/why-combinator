from __future__ import annotations

import uuid

from celery import shared_task

from app.orchestrator.jobs import run_checkpoint_score_job, run_complete_run_job, run_hacker_job, run_judge_job
from app.queue.budget import create_redis_client, reserve_budget, task_cost_from_env
from app.queue.dedup import claim_score_job_dedup_key


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


@shared_task(
    name="app.queue.jobs.complete_run",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def complete_run(self, run_id: str) -> dict[str, str]:
    return run_complete_run_job(run_id)


def enqueue_submission_score_job(submission_id: uuid.UUID, checkpoint_id: str) -> dict[str, str]:
    redis_client = create_redis_client()
    try:
        claimed = claim_score_job_dedup_key(redis_client, submission_id, checkpoint_id)
    finally:
        redis_client.close()
    if not claimed:
        return {
            "job_type": "score-submission",
            "submission_id": str(submission_id),
            "checkpoint_id": checkpoint_id,
            "status": "duplicate_suppressed",
        }
    score_submission.delay(str(submission_id), checkpoint_id)
    return {
        "job_type": "score-submission",
        "submission_id": str(submission_id),
        "checkpoint_id": checkpoint_id,
        "status": "queued",
    }


@shared_task(
    name="app.queue.jobs.score_submission",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def score_submission(self, submission_id: str, checkpoint_id: str) -> dict[str, str]:
    return {
        "job_type": "score-submission",
        "submission_id": submission_id,
        "checkpoint_id": checkpoint_id,
        "status": "queued",
    }
