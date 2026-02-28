from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JudgePromptInput:
    domain_profile: str
    scoring_rubric: dict[str, float]
    penalty_policy: dict[str, float]
    submission_summary: str


def render_judge_agent_prompt(payload: JudgePromptInput) -> str:
    rubric_lines = "\n".join(f"- {criterion}: weight={weight}" for criterion, weight in payload.scoring_rubric.items())
    penalty_lines = "\n".join(f"- {penalty}: weight={weight}" for penalty, weight in payload.penalty_policy.items())
    return (
        "You are a Judge Agent for a hackathon submission.\n"
        f"Domain profile: {payload.domain_profile}\n"
        "Scoring rubric:\n"
        f"{rubric_lines or '- none provided'}\n"
        "Penalty policy:\n"
        f"{penalty_lines or '- none provided'}\n"
        f"Submission summary: {payload.submission_summary}\n"
        "Return a normalized score between 0 and 1 and a concise rationale."
    )
