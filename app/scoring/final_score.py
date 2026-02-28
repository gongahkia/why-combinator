from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ScoreComponents:
    quality: float
    novelty: float
    feasibility: float
    criteria: float
    similarity_penalty: float
    too_safe_penalty: float
    non_production_penalty: float = 0.0


@dataclass(frozen=True)
class ActiveWeightsSnapshot:
    quality: float
    novelty: float
    feasibility: float
    criteria: float
    similarity_penalty: float
    too_safe_penalty: float
    non_production_penalty: float = 1.0


@dataclass(frozen=True)
class FinalScoreBreakdown:
    weighted_positive: float
    weighted_penalties: float
    final_score: float
    components: ScoreComponents
    weights: ActiveWeightsSnapshot

    def as_payload(self) -> dict[str, object]:
        return {
            "weighted_positive": round(self.weighted_positive, 6),
            "weighted_penalties": round(self.weighted_penalties, 6),
            "final_score": round(self.final_score, 6),
            "components": asdict(self.components),
            "weights": asdict(self.weights),
        }


def compose_final_score(components: ScoreComponents, weights: ActiveWeightsSnapshot) -> FinalScoreBreakdown:
    weighted_positive = (
        components.quality * weights.quality
        + components.novelty * weights.novelty
        + components.feasibility * weights.feasibility
        + components.criteria * weights.criteria
    )
    weighted_penalties = (
        components.similarity_penalty * weights.similarity_penalty
        + components.too_safe_penalty * weights.too_safe_penalty
        + components.non_production_penalty * weights.non_production_penalty
    )
    final_score = weighted_positive - weighted_penalties
    return FinalScoreBreakdown(
        weighted_positive=weighted_positive,
        weighted_penalties=weighted_penalties,
        final_score=round(final_score, 6),
        components=components,
        weights=weights,
    )
