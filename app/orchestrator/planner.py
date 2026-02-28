from __future__ import annotations

from dataclasses import dataclass

from app.orchestrator.policy import map_complexity_slider_to_allocation


@dataclass(frozen=True)
class AdaptivePlan:
    budget_for_new_ideas: float
    budget_for_refinement: float
    checkpoint_budget: float


def build_adaptive_plan(
    remaining_budget: float,
    checkpoints_remaining: int,
    complexity_slider: float,
    recent_acceptance_rate: float,
) -> AdaptivePlan:
    if checkpoints_remaining <= 0:
        raise ValueError("checkpoints_remaining must be positive")
    checkpoint_budget = max(0.0, remaining_budget / checkpoints_remaining)

    base_allocation = map_complexity_slider_to_allocation(complexity_slider)
    acceptance_adjustment = max(-0.2, min(0.2, 0.25 - recent_acceptance_rate))
    exploration_share = max(0.1, min(0.9, base_allocation.exploration_time_share + acceptance_adjustment))
    refinement_share = 1.0 - exploration_share

    return AdaptivePlan(
        budget_for_new_ideas=round(checkpoint_budget * exploration_share, 4),
        budget_for_refinement=round(checkpoint_budget * refinement_share, 4),
        checkpoint_budget=round(checkpoint_budget, 4),
    )
