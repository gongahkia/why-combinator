from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class JobResult:
    job_type: str
    run_id: str
    status: str



def run_hacker_job(run_id: str) -> dict[str, str]:
    return asdict(JobResult(job_type="hacker-run", run_id=run_id, status="queued"))



def run_judge_job(run_id: str) -> dict[str, str]:
    return asdict(JobResult(job_type="judge-run", run_id=run_id, status="queued"))



def run_checkpoint_score_job(run_id: str) -> dict[str, str]:
    return asdict(JobResult(job_type="checkpoint-score", run_id=run_id, status="queued"))
