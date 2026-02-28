from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RiskAppetite = Literal["conservative", "balanced", "aggressive"]


@dataclass(frozen=True)
class ExplorationConstraints:
    max_parallel_ideas: int
    max_subagent_depth: int
    novelty_penalty_sensitivity: float


def map_risk_appetite_to_constraints(risk_appetite: RiskAppetite) -> ExplorationConstraints:
    mapping: dict[RiskAppetite, ExplorationConstraints] = {
        "conservative": ExplorationConstraints(max_parallel_ideas=2, max_subagent_depth=1, novelty_penalty_sensitivity=1.2),
        "balanced": ExplorationConstraints(max_parallel_ideas=4, max_subagent_depth=2, novelty_penalty_sensitivity=1.0),
        "aggressive": ExplorationConstraints(max_parallel_ideas=6, max_subagent_depth=3, novelty_penalty_sensitivity=0.8),
    }
    return mapping[risk_appetite]
