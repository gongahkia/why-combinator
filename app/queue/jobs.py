from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any

from celery import shared_task, signals

from app.orchestrator.jobs import run_checkpoint_score_job, run_complete_run_job, run_hacker_job, run_judge_job
from app.queue.budget import create_redis_client, reserve_budget, task_cost_from_env
from app.queue.dead_letter import persist_dead_letter_event
from app.queue.dedup import claim_score_job_dedup_key
from app.queue.recovery import (
    clear_in_flight_task,
    list_in_flight_tasks,
    load_worker_drain_timeout_seconds,
    mark_recoverable_task,
    track_in_flight_task,
)

_ACTIVE_TASK_IDS: set[str] = set()
_ACTIVE_TASK_IDS_LOCK = threading.Lock()


def _normalize_jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_normalize_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_jsonable(item) for key, item in value.items()}
    return str(value)


def _track_task_started(task_id: str, task_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    with _ACTIVE_TASK_IDS_LOCK:
        _ACTIVE_TASK_IDS.add(task_id)
    redis_client = create_redis_client()
    try:
        track_in_flight_task(
            redis_client,
            task_id=task_id,
            task_name=task_name,
            args=_normalize_jsonable(list(args)),
            kwargs=_normalize_jsonable(kwargs),
            worker_pid=os.getpid(),
            worker_hostname=os.getenv("HOSTNAME"),
        )
    finally:
        redis_client.close()


def _track_task_finished(task_id: str | None) -> None:
    if not task_id:
        return
    with _ACTIVE_TASK_IDS_LOCK:
        _ACTIVE_TASK_IDS.discard(task_id)
    redis_client = create_redis_client()
    try:
        clear_in_flight_task(redis_client, task_id)
    finally:
        redis_client.close()


@signals.task_prerun.connect
def _on_task_prerun(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    args: tuple[Any, ...] | None = None,
    kwargs: dict[str, Any] | None = None,
    **_: Any,
) -> None:
    if not task_id or task is None:
        return
    task_name = str(getattr(task, "name", ""))
    if not task_name.startswith("app.queue.jobs."):
        return
    _track_task_started(task_id, task_name, args or (), kwargs or {})


@signals.task_postrun.connect
def _on_task_postrun(
    sender: Any = None,
    task_id: str | None = None,
    **_: Any,
) -> None:
    task_name = str(getattr(sender, "name", ""))
    if task_name.startswith("app.queue.jobs."):
        _track_task_finished(task_id)


@signals.task_revoked.connect
def _on_task_revoked(request: Any = None, **_: Any) -> None:
    task_id = str(getattr(request, "id", "")) if request is not None else ""
    if task_id:
        _track_task_finished(task_id)


@signals.worker_shutting_down.connect
def _on_worker_shutting_down(**_: Any) -> None:
    deadline = time.monotonic() + load_worker_drain_timeout_seconds()
    while time.monotonic() < deadline:
        with _ACTIVE_TASK_IDS_LOCK:
            if not _ACTIVE_TASK_IDS:
                return
        time.sleep(0.2)

    with _ACTIVE_TASK_IDS_LOCK:
        remaining_ids = set(_ACTIVE_TASK_IDS)

    redis_client = create_redis_client()
    try:
        for payload in list_in_flight_tasks(redis_client):
            task_id = str(payload.get("task_id", ""))
            worker_pid = int(payload.get("worker_pid", -1))
            if task_id not in remaining_ids or worker_pid != os.getpid():
                continue
            mark_recoverable_task(
                redis_client,
                task_payload=payload,
                reason="worker_shutdown_drain_timeout",
            )
    finally:
        redis_client.close()


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


def _checkpoint_run_lock_key(run_id: str) -> str:
    return f"lock:checkpoint-score:{run_id}"


@shared_task(name="app.queue.jobs.hacker_run", bind=True)
def hacker_run(self, run_id: str) -> dict[str, str]:
    max_retries = 3
    try:
        accepted, payload = _with_budget_guard(run_id, "hacker-run", default_cost=10)
        if not accepted:
            return payload
        return run_hacker_job(run_id)
    except Exception as exc:  # noqa: BLE001
        if self.request.retries >= max_retries:
            persist_dead_letter_event("hacker-run", run_id, str(exc), self.request.retries)
            return {"job_type": "hacker-run", "run_id": run_id, "status": "dead_lettered", "reason": str(exc)}
        raise self.retry(exc=exc, countdown=2**self.request.retries, max_retries=max_retries)


@shared_task(name="app.queue.jobs.judge_run", bind=True)
def judge_run(self, run_id: str) -> dict[str, str]:
    max_retries = 3
    try:
        accepted, payload = _with_budget_guard(run_id, "judge-run", default_cost=5)
        if not accepted:
            return payload
        return run_judge_job(run_id)
    except Exception as exc:  # noqa: BLE001
        if self.request.retries >= max_retries:
            persist_dead_letter_event("judge-run", run_id, str(exc), self.request.retries)
            return {"job_type": "judge-run", "run_id": run_id, "status": "dead_lettered", "reason": str(exc)}
        raise self.retry(exc=exc, countdown=2**self.request.retries, max_retries=max_retries)


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
    redis_client = create_redis_client()
    lock = redis_client.lock(_checkpoint_run_lock_key(run_id), timeout=60, blocking=False)
    if not lock.acquire(blocking=False):
        redis_client.close()
        return {
            "job_type": "checkpoint-score",
            "run_id": run_id,
            "status": "lock_not_acquired",
        }
    try:
        return run_checkpoint_score_job(run_id)
    finally:
        lock.release()
        redis_client.close()


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
