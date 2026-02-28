from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunAdmissionDecision:
    allowed: bool
    reason: str
    active_tasks: int
    threshold: int


def load_run_admission_max_active_tasks() -> int:
    return int(os.getenv("RUN_ADMISSION_MAX_ACTIVE_TASKS", "200"))


def load_run_admission_watermark_ratio() -> float:
    return float(os.getenv("RUN_ADMISSION_WATERMARK_RATIO", "0.8"))


def evaluate_run_admission_capacity(inspect_client: Any) -> RunAdmissionDecision:
    max_active_tasks = max(1, load_run_admission_max_active_tasks())
    watermark_ratio = max(0.0, min(1.0, load_run_admission_watermark_ratio()))
    threshold = max(1, int(max_active_tasks * watermark_ratio))
    try:
        active_payload = inspect_client.active() or {}
        reserved_payload = inspect_client.reserved() or {}
    except Exception:
        return RunAdmissionDecision(
            allowed=True,
            reason="inspection_unavailable",
            active_tasks=0,
            threshold=threshold,
        )

    active_tasks = sum(len(tasks) for tasks in active_payload.values())
    reserved_tasks = sum(len(tasks) for tasks in reserved_payload.values())
    observed_tasks = active_tasks + reserved_tasks

    if observed_tasks >= threshold:
        return RunAdmissionDecision(
            allowed=False,
            reason="worker_capacity_watermark_exceeded",
            active_tasks=observed_tasks,
            threshold=threshold,
        )
    return RunAdmissionDecision(
        allowed=True,
        reason="ok",
        active_tasks=observed_tasks,
        threshold=threshold,
    )
