from __future__ import annotations

from app.queue import jobs as queue_jobs


def test_budget_exhaustion_blocks_new_tasks_but_allows_finalization(monkeypatch) -> None:
    def fake_budget_guard(run_id: str, task_name: str, default_cost: int) -> tuple[bool, dict[str, str]]:
        return False, {
            "job_type": task_name,
            "run_id": run_id,
            "status": "budget_exhausted",
            "budget_remaining": "0",
        }

    def fake_complete_run_job(run_id: str, trace_id: str | None = None) -> dict[str, str]:
        return {
            "job_type": "run-complete",
            "run_id": run_id,
            "status": "completed",
            "trace_id": trace_id or "",
        }

    monkeypatch.setattr(queue_jobs, "_with_budget_guard", fake_budget_guard)
    monkeypatch.setattr(queue_jobs, "run_complete_run_job", fake_complete_run_job)
    monkeypatch.setattr(queue_jobs, "_record_run_worker_heartbeat", lambda run_id: None)

    blocked = queue_jobs.hacker_run.run("run-1", "trace-budget")
    assert blocked["status"] == "budget_exhausted"
    assert blocked["job_type"] == "hacker-run"

    finalization = queue_jobs.complete_run.run("run-1", "trace-budget")
    assert finalization["status"] == "completed"
    assert finalization["job_type"] == "run-complete"
    assert finalization["trace_id"] == "trace-budget"
