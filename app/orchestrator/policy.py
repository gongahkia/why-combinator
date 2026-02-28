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


@dataclass(frozen=True)
class ComplexityAllocation:
    target_idea_count: int
    target_depth: int
    exploration_time_share: float
    refinement_time_share: float


def map_complexity_slider_to_allocation(slider_value: float) -> ComplexityAllocation:
    bounded = max(0.0, min(1.0, slider_value))
    target_idea_count = max(1, round(8 - (bounded * 6)))
    target_depth = max(1, round(1 + (bounded * 4)))
    refinement_time_share = round(0.3 + (bounded * 0.5), 2)
    exploration_time_share = round(1.0 - refinement_time_share, 2)
    return ComplexityAllocation(
        target_idea_count=target_idea_count,
        target_depth=target_depth,
        exploration_time_share=exploration_time_share,
        refinement_time_share=refinement_time_share,
    )
