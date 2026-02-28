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
class NoveltyPenaltySensitivityPolicy:
    similarity_threshold: float
    too_safe_threshold: float
    sensitivity_multiplier: float


def resolve_novelty_penalty_sensitivity_policy(risk_appetite: str) -> NoveltyPenaltySensitivityPolicy:
    mapping: dict[str, NoveltyPenaltySensitivityPolicy] = {
        "conservative": NoveltyPenaltySensitivityPolicy(
            similarity_threshold=0.0,
            too_safe_threshold=0.0,
            sensitivity_multiplier=1.2,
        ),
        "balanced": NoveltyPenaltySensitivityPolicy(
            similarity_threshold=0.0,
            too_safe_threshold=0.0,
            sensitivity_multiplier=1.0,
        ),
        "aggressive": NoveltyPenaltySensitivityPolicy(
            similarity_threshold=0.2,
            too_safe_threshold=0.2,
            sensitivity_multiplier=0.8,
        ),
    }
    return mapping.get(risk_appetite, mapping["balanced"])


def _apply_thresholded_penalty(raw_value: float, threshold: float, multiplier: float) -> float:
    bounded = max(0.0, min(1.0, raw_value))
    bounded_threshold = max(0.0, min(1.0, threshold))
    if bounded <= bounded_threshold:
        return 0.0
    scaled = (bounded - bounded_threshold) / max(1e-9, 1.0 - bounded_threshold)
    adjusted = scaled * max(0.0, multiplier)
    return round(max(0.0, min(1.0, adjusted)), 6)


def apply_risk_appetite_novelty_penalty_sensitivity(
    risk_appetite: str,
    similarity_penalty: float,
    too_safe_penalty: float,
) -> tuple[float, float, NoveltyPenaltySensitivityPolicy]:
    policy = resolve_novelty_penalty_sensitivity_policy(risk_appetite)
    adjusted_similarity = _apply_thresholded_penalty(
        similarity_penalty,
        policy.similarity_threshold,
        policy.sensitivity_multiplier,
    )
    adjusted_too_safe = _apply_thresholded_penalty(
        too_safe_penalty,
        policy.too_safe_threshold,
        policy.sensitivity_multiplier,
    )
    return adjusted_similarity, adjusted_too_safe, policy


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


@dataclass(frozen=True)
class ArtifactSophisticationPolicy:
    target_sophistication: float
    tolerance: float


def resolve_artifact_sophistication_policy(complexity_slider: float) -> ArtifactSophisticationPolicy:
    bounded = max(0.0, min(1.0, complexity_slider))
    target = round(0.35 + (bounded * 0.5), 6)
    tolerance = round(0.35 - (bounded * 0.15), 6)
    return ArtifactSophisticationPolicy(
        target_sophistication=target,
        tolerance=max(0.1, tolerance),
    )
