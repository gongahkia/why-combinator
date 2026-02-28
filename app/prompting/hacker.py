from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HackerPromptInput:
    challenge_title: str
    challenge_prompt: str
    criteria: dict[str, float]
    risk_appetite: str
    complexity_slider: float
    run_seed: int = 0
    agent_seed: int = 0
    agent_label: str = "hacker"


def render_hacker_agent_prompt(payload: HackerPromptInput) -> str:
    sorted_criteria = sorted(payload.criteria.items(), key=lambda item: item[0])
    criteria_lines = "\n".join(f"- {name}: weight={weight}" for name, weight in sorted_criteria)
    return (
        "You are a Hacker Agent in a timed AI hackathon.\n"
        f"Challenge title: {payload.challenge_title}\n"
        f"Challenge prompt: {payload.challenge_prompt}\n"
        "Scoring criteria and weights:\n"
        f"{criteria_lines or '- none provided'}\n"
        f"Risk appetite: {payload.risk_appetite}\n"
        f"Complexity slider: {payload.complexity_slider:.2f}\n"
        f"Replay run seed: {payload.run_seed}\n"
        f"Agent seed ({payload.agent_label}): {payload.agent_seed}\n"
        "Use the provided seeds when any stochastic choice is needed so replay mode remains deterministic.\n"
        "Produce one concrete MVP attempt with runnable output, concise README, and value hypothesis."
    )
