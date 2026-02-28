from __future__ import annotations

from celery import Celery

from app.config import load_settings

settings = load_settings()

celery_app = Celery(
    "hackathon",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.queue.jobs"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.queue.jobs.hacker_run": {"queue": "hacker-run"},
        "app.queue.jobs.judge_run": {"queue": "judge-run"},
        "app.queue.jobs.checkpoint_score": {"queue": "checkpoint-score"},
        "app.queue.jobs.complete_run": {"queue": "run-complete"},
    },
)
