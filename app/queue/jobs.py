from __future__ import annotations

from celery import shared_task

from app.orchestrator.jobs import run_checkpoint_score_job, run_hacker_job, run_judge_job


@shared_task(name="app.queue.jobs.hacker_run", bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def hacker_run(self, run_id: str) -> dict[str, str]:
    return run_hacker_job(run_id)


@shared_task(name="app.queue.jobs.judge_run", bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def judge_run(self, run_id: str) -> dict[str, str]:
    return run_judge_job(run_id)


@shared_task(
    name="app.queue.jobs.checkpoint_score",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def checkpoint_score(self, run_id: str) -> dict[str, str]:
    return run_checkpoint_score_job(run_id)
