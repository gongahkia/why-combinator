from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from app.sandbox.runner import HackerAgentRunSpec, HackerAgentRunner, load_hacker_runner_limits_from_env


@dataclass
class JobResult:
    job_type: str
    run_id: str
    status: str



def run_hacker_job(run_id: str) -> dict[str, str]:
    if os.getenv("HACKER_RUNNER_ENABLED", "false").lower() != "true":
        return asdict(JobResult(job_type="hacker-run", run_id=run_id, status="runner-disabled"))

    image = os.getenv("HACKER_RUNNER_IMAGE", "alpine:3.20")
    command = [
        "sh",
        "-lc",
        f"echo running_hacker_agent_for_run={run_id}",
    ]
    runner = HackerAgentRunner()
    result = runner.run(
        spec=HackerAgentRunSpec(
            agent_id=run_id,
            image=image,
            command=command,
            env={"RUN_ID": run_id},
        ),
        limits=load_hacker_runner_limits_from_env(),
    )
    return {
        "job_type": "hacker-run",
        "run_id": run_id,
        "status": "timeout" if result.timed_out else "completed",
        "container_name": result.container_name,
        "exit_code": "" if result.exit_code is None else str(result.exit_code),
    }



def run_judge_job(run_id: str) -> dict[str, str]:
    return asdict(JobResult(job_type="judge-run", run_id=run_id, status="queued"))



def run_checkpoint_score_job(run_id: str) -> dict[str, str]:
    return asdict(JobResult(job_type="checkpoint-score", run_id=run_id, status="queued"))
