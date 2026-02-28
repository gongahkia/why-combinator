from __future__ import annotations

import asyncio
import os
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from celery import shared_task, signals
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import load_settings
from app.observability.trace import ensure_trace_id
from app.observability.trace import new_trace_id
from app.orchestrator.jobs import (
    run_checkpoint_score_job,
    run_complete_run_job,
    run_hacker_job,
    run_judge_job,
    run_outbox_relay_job,
    run_scheduler_heartbeat_monitor_job,
    run_stale_run_heartbeat_watchdog_job,
)
from app.queue.checkpoint_backfill import (
    clear_failed_checkpoint_backfill,
    list_failed_checkpoint_backfills,
    record_failed_checkpoint_backfill,
)
from app.queue.budget import create_redis_client, reserve_budget, task_cost_from_env
from app.queue.dead_letter import persist_dead_letter_event
from app.queue.dedup import claim_score_job_dedup_key
from app.queue.recovery import (
    clear_in_flight_task,
    detect_orphaned_in_flight_tasks,
    list_in_flight_tasks,
    list_recoverable_tasks,
    load_orphan_stale_threshold_seconds,
    load_worker_drain_timeout_seconds,
    mark_recoverable_task,
    remove_recoverable_task,
    track_in_flight_task,
)
from app.scheduler.run_timeout import run_worker_heartbeat_key
from app.sandbox.concurrency import acquire_run_hacker_container_slot, release_run_hacker_container_slot

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


def _track_task_started(
    task_id: str,
    task_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    worker_hostname: str | None,
) -> None:
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
            worker_hostname=worker_hostname or os.getenv("HOSTNAME"),
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
    request_obj = getattr(task, "request", None)
    worker_hostname = str(getattr(request_obj, "hostname", "")) if request_obj is not None else None
    _track_task_started(task_id, task_name, args or (), kwargs or {}, worker_hostname)


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


def _coerce_task_args(payload: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    args = payload.get("args", [])
    kwargs = payload.get("kwargs", {})
    if not isinstance(args, list):
        args = []
    if not isinstance(kwargs, dict):
        kwargs = {}
    return args, kwargs


@shared_task(
    name="app.queue.jobs.recover_orphaned_tasks",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def recover_orphaned_tasks(self) -> dict[str, str]:
    redis_client = create_redis_client()
    inspect_client = self.app.control.inspect(timeout=1.0)
    active_workers = set((inspect_client.ping() or {}).keys())
    stale_threshold = load_orphan_stale_threshold_seconds()
    orphaned = []
    recovered = 0
    try:
        orphaned = detect_orphaned_in_flight_tasks(
            redis_client,
            active_worker_hostnames=active_workers,
            stale_threshold_seconds=stale_threshold,
        )
        for payload in orphaned:
            mark_recoverable_task(redis_client, task_payload=payload, reason="worker_crash_detected")

        for recoverable in list_recoverable_tasks(redis_client):
            task_name = str(recoverable.get("task_name", ""))
            task_id = str(recoverable.get("task_id", ""))
            if not task_name or not task_id or task_name == "app.queue.jobs.recover_orphaned_tasks":
                continue
            args, kwargs = _coerce_task_args(recoverable)
            self.app.send_task(task_name, args=args, kwargs=kwargs)
            remove_recoverable_task(redis_client, task_id)
            recovered += 1
    finally:
        redis_client.close()

    return {
        "job_type": "recover-orphaned",
        "status": "completed",
        "orphaned_detected": str(len(orphaned)),
        "requeued": str(recovered),
    }


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


def _record_run_worker_heartbeat(run_id: str) -> None:
    redis_client = create_redis_client()
    try:
        redis_client.set(run_worker_heartbeat_key(run_id), datetime.now(UTC).isoformat())
    finally:
        redis_client.close()


def load_checkpoint_backfill_max_enqueues() -> int:
    return int(os.getenv("CHECKPOINT_BACKFILL_MAX_ENQUEUES", "25"))


def load_checkpoint_backfill_retry_delay_seconds() -> int:
    return int(os.getenv("CHECKPOINT_BACKFILL_RETRY_DELAY_SECONDS", "60"))


def _is_temporary_dependency_failure(exc: Exception) -> bool:
    text_value = f"{exc.__class__.__name__}:{exc}".lower()
    dependency_failure_tokens = (
        "connection refused",
        "connection reset",
        "temporarily unavailable",
        "timeout",
        "timed out",
        "could not connect",
        "failed to connect",
        "server closed the connection",
        "name or service not known",
        "temporary failure in name resolution",
        "database is locked",
        "redis",
        "postgres",
        "asyncpg",
    )
    return any(token in text_value for token in dependency_failure_tokens)


async def _probe_database_connectivity(database_url: str) -> bool:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        await engine.dispose()


def _dependencies_recovered_for_checkpoint_backfill() -> bool:
    redis_client = create_redis_client()
    try:
        redis_client.ping()
    except Exception:  # noqa: BLE001
        return False
    finally:
        redis_client.close()

    settings = load_settings()
    try:
        return asyncio.run(_probe_database_connectivity(settings.database_url))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_probe_database_connectivity(settings.database_url))
        finally:
            loop.close()


@shared_task(name="app.queue.jobs.hacker_run", bind=True)
def hacker_run(
    self,
    run_id: str,
    trace_id: str | None = None,
    agent_id: str | None = None,
    run_seed: int | None = None,
) -> dict[str, str]:
    effective_trace_id = ensure_trace_id(trace_id)
    max_retries = 3
    try:
        _record_run_worker_heartbeat(run_id)
        accepted, payload = _with_budget_guard(run_id, "hacker-run", default_cost=10)
        if not accepted:
            return {**payload, "trace_id": effective_trace_id}
        redis_client = create_redis_client()
        try:
            slot_acquired, remaining_slots = acquire_run_hacker_container_slot(redis_client, run_id)
        finally:
            redis_client.close()
        if not slot_acquired:
            return {
                "job_type": "hacker-run",
                "run_id": run_id,
                "status": "concurrency_limited",
                "remaining_slots": str(remaining_slots),
                "trace_id": effective_trace_id,
            }
        try:
            return run_hacker_job(run_id, trace_id=effective_trace_id, agent_id=agent_id, run_seed=run_seed)
        finally:
            redis_client = create_redis_client()
            try:
                release_run_hacker_container_slot(redis_client, run_id)
            finally:
                redis_client.close()
    except Exception as exc:  # noqa: BLE001
        if self.request.retries >= max_retries:
            persist_dead_letter_event("hacker-run", run_id, str(exc), self.request.retries)
            return {
                "job_type": "hacker-run",
                "run_id": run_id,
                "status": "dead_lettered",
                "reason": str(exc),
                "trace_id": effective_trace_id,
            }
        raise self.retry(exc=exc, countdown=2**self.request.retries, max_retries=max_retries)


@shared_task(name="app.queue.jobs.judge_run", bind=True)
def judge_run(self, run_id: str, trace_id: str | None = None) -> dict[str, str]:
    effective_trace_id = ensure_trace_id(trace_id)
    max_retries = 3
    try:
        _record_run_worker_heartbeat(run_id)
        accepted, payload = _with_budget_guard(run_id, "judge-run", default_cost=5)
        if not accepted:
            return {**payload, "trace_id": effective_trace_id}
        return run_judge_job(run_id, trace_id=effective_trace_id)
    except Exception as exc:  # noqa: BLE001
        if self.request.retries >= max_retries:
            persist_dead_letter_event("judge-run", run_id, str(exc), self.request.retries)
            return {
                "job_type": "judge-run",
                "run_id": run_id,
                "status": "dead_lettered",
                "reason": str(exc),
                "trace_id": effective_trace_id,
            }
        raise self.retry(exc=exc, countdown=2**self.request.retries, max_retries=max_retries)


@shared_task(name="app.queue.jobs.checkpoint_score", bind=True)
def checkpoint_score(self, run_id: str, trace_id: str | None = None) -> dict[str, str]:
    effective_trace_id = ensure_trace_id(trace_id)
    max_retries = 3
    _record_run_worker_heartbeat(run_id)
    accepted, payload = _with_budget_guard(run_id, "checkpoint-score", default_cost=2)
    if not accepted:
        return {**payload, "trace_id": effective_trace_id}
    redis_client = create_redis_client()
    lock = redis_client.lock(_checkpoint_run_lock_key(run_id), timeout=60, blocking=False)
    if not lock.acquire(blocking=False):
        redis_client.close()
        return {
            "job_type": "checkpoint-score",
            "run_id": run_id,
            "status": "lock_not_acquired",
            "trace_id": effective_trace_id,
        }
    try:
        return run_checkpoint_score_job(run_id, trace_id=effective_trace_id)
    except Exception as exc:  # noqa: BLE001
        if _is_temporary_dependency_failure(exc):
            record_failed_checkpoint_backfill(
                redis_client,
                run_id=run_id,
                trace_id=effective_trace_id,
                reason=str(exc),
            )
            backfill_failed_checkpoints.apply_async(
                kwargs={"trace_id": new_trace_id()},
                countdown=max(1, load_checkpoint_backfill_retry_delay_seconds()),
            )
            return {
                "job_type": "checkpoint-score",
                "run_id": run_id,
                "status": "dependency_failed_backfill_queued",
                "reason": str(exc),
                "trace_id": effective_trace_id,
            }
        if self.request.retries >= max_retries:
            persist_dead_letter_event("checkpoint-score", run_id, str(exc), self.request.retries)
            return {
                "job_type": "checkpoint-score",
                "run_id": run_id,
                "status": "dead_lettered",
                "reason": str(exc),
                "trace_id": effective_trace_id,
            }
        raise self.retry(exc=exc, countdown=2**self.request.retries, max_retries=max_retries)
    finally:
        lock.release()
        redis_client.close()


@shared_task(
    name="app.queue.jobs.backfill_failed_checkpoints",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def backfill_failed_checkpoints(self, trace_id: str | None = None) -> dict[str, str]:
    effective_trace_id = ensure_trace_id(trace_id)
    redis_client = create_redis_client()
    try:
        pending_backfills = list_failed_checkpoint_backfills(redis_client)
        if not pending_backfills:
            return {
                "job_type": "checkpoint-backfill",
                "status": "completed",
                "enqueued": "0",
                "remaining": "0",
                "trace_id": effective_trace_id,
            }

        if not _dependencies_recovered_for_checkpoint_backfill():
            backfill_failed_checkpoints.apply_async(
                kwargs={"trace_id": new_trace_id()},
                countdown=max(1, load_checkpoint_backfill_retry_delay_seconds()),
            )
            return {
                "job_type": "checkpoint-backfill",
                "status": "dependencies_unhealthy",
                "enqueued": "0",
                "remaining": str(len(pending_backfills)),
                "trace_id": effective_trace_id,
            }

        max_enqueues = max(1, load_checkpoint_backfill_max_enqueues())
        enqueued = 0
        for payload in pending_backfills[:max_enqueues]:
            run_id = str(payload.get("run_id", "")).strip()
            if not run_id:
                continue
            checkpoint_score.delay(run_id, new_trace_id())
            clear_failed_checkpoint_backfill(redis_client, run_id)
            enqueued += 1

        return {
            "job_type": "checkpoint-backfill",
            "status": "completed",
            "enqueued": str(enqueued),
            "remaining": str(max(0, len(pending_backfills) - enqueued)),
            "trace_id": effective_trace_id,
        }
    finally:
        redis_client.close()


@shared_task(
    name="app.queue.jobs.relay_outbox_events",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def relay_outbox_events(self, trace_id: str | None = None) -> dict[str, str]:
    effective_trace_id = ensure_trace_id(trace_id)
    return run_outbox_relay_job(trace_id=effective_trace_id)


@shared_task(
    name="app.queue.jobs.scheduler_heartbeat_monitor",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def scheduler_heartbeat_monitor(self, trace_id: str | None = None) -> dict[str, str]:
    effective_trace_id = ensure_trace_id(trace_id)
    return run_scheduler_heartbeat_monitor_job(trace_id=effective_trace_id)


@shared_task(
    name="app.queue.jobs.complete_run",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def complete_run(self, run_id: str, trace_id: str | None = None) -> dict[str, str]:
    effective_trace_id = ensure_trace_id(trace_id)
    _record_run_worker_heartbeat(run_id)
    return run_complete_run_job(run_id, trace_id=effective_trace_id)


@shared_task(
    name="app.queue.jobs.run_heartbeat_watchdog",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def run_heartbeat_watchdog(self, trace_id: str | None = None) -> dict[str, str]:
    effective_trace_id = ensure_trace_id(trace_id)
    return run_stale_run_heartbeat_watchdog_job(trace_id=effective_trace_id)


def enqueue_submission_score_job(
    submission_id: uuid.UUID,
    checkpoint_id: str,
    trace_id: str | None = None,
) -> dict[str, str]:
    effective_trace_id = ensure_trace_id(trace_id)
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
            "trace_id": effective_trace_id,
        }
    score_submission.delay(str(submission_id), checkpoint_id, effective_trace_id)
    return {
        "job_type": "score-submission",
        "submission_id": str(submission_id),
        "checkpoint_id": checkpoint_id,
        "status": "queued",
        "trace_id": effective_trace_id,
    }


@shared_task(
    name="app.queue.jobs.score_submission",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def score_submission(self, submission_id: str, checkpoint_id: str, trace_id: str | None = None) -> dict[str, str]:
    effective_trace_id = ensure_trace_id(trace_id)
    return {
        "job_type": "score-submission",
        "submission_id": submission_id,
        "checkpoint_id": checkpoint_id,
        "status": "queued",
        "trace_id": effective_trace_id,
    }
