from __future__ import annotations

import math
import os
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


@dataclass(frozen=True)
class ScoreComponentBounds:
    quality_floor: float
    quality_cap: float
    novelty_floor: float
    novelty_cap: float
    feasibility_floor: float
    feasibility_cap: float
    criteria_floor: float
    criteria_cap: float
    similarity_penalty_floor: float
    similarity_penalty_cap: float
    too_safe_penalty_floor: float
    too_safe_penalty_cap: float
    non_production_penalty_floor: float
    non_production_penalty_cap: float


class ScoreComponentBoundsValidationError(ValueError):
    """Raised when score component floor/cap configuration is invalid."""


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default))
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ScoreComponentBoundsValidationError(f"{name} must be a float value") from exc


def _validate_floor_cap_pair(name: str, floor: float, cap: float) -> None:
    if not math.isfinite(floor):
        raise ScoreComponentBoundsValidationError(f"{name}_floor must be finite")
    if not math.isfinite(cap):
        raise ScoreComponentBoundsValidationError(f"{name}_cap must be finite")
    if floor < 0.0 or floor > 1.0:
        raise ScoreComponentBoundsValidationError(f"{name}_floor must be between 0.0 and 1.0")
    if cap < 0.0 or cap > 1.0:
        raise ScoreComponentBoundsValidationError(f"{name}_cap must be between 0.0 and 1.0")
    if floor > cap:
        raise ScoreComponentBoundsValidationError(f"{name}_floor must be less than or equal to {name}_cap")


def validate_score_component_bounds(bounds: ScoreComponentBounds) -> None:
    _validate_floor_cap_pair("quality", bounds.quality_floor, bounds.quality_cap)
    _validate_floor_cap_pair("novelty", bounds.novelty_floor, bounds.novelty_cap)
    _validate_floor_cap_pair("feasibility", bounds.feasibility_floor, bounds.feasibility_cap)
    _validate_floor_cap_pair("criteria", bounds.criteria_floor, bounds.criteria_cap)
    _validate_floor_cap_pair(
        "similarity_penalty",
        bounds.similarity_penalty_floor,
        bounds.similarity_penalty_cap,
    )
    _validate_floor_cap_pair(
        "too_safe_penalty",
        bounds.too_safe_penalty_floor,
        bounds.too_safe_penalty_cap,
    )
    _validate_floor_cap_pair(
        "non_production_penalty",
        bounds.non_production_penalty_floor,
        bounds.non_production_penalty_cap,
    )


def load_score_component_bounds() -> ScoreComponentBounds:
    bounds = ScoreComponentBounds(
        quality_floor=_env_float("SCORE_COMPONENT_FLOOR_QUALITY", 0.0),
        quality_cap=_env_float("SCORE_COMPONENT_CAP_QUALITY", 1.0),
        novelty_floor=_env_float("SCORE_COMPONENT_FLOOR_NOVELTY", 0.0),
        novelty_cap=_env_float("SCORE_COMPONENT_CAP_NOVELTY", 1.0),
        feasibility_floor=_env_float("SCORE_COMPONENT_FLOOR_FEASIBILITY", 0.0),
        feasibility_cap=_env_float("SCORE_COMPONENT_CAP_FEASIBILITY", 1.0),
        criteria_floor=_env_float("SCORE_COMPONENT_FLOOR_CRITERIA", 0.0),
        criteria_cap=_env_float("SCORE_COMPONENT_CAP_CRITERIA", 1.0),
        similarity_penalty_floor=_env_float("SCORE_COMPONENT_FLOOR_SIMILARITY_PENALTY", 0.0),
        similarity_penalty_cap=_env_float("SCORE_COMPONENT_CAP_SIMILARITY_PENALTY", 0.75),
        too_safe_penalty_floor=_env_float("SCORE_COMPONENT_FLOOR_TOO_SAFE_PENALTY", 0.0),
        too_safe_penalty_cap=_env_float("SCORE_COMPONENT_CAP_TOO_SAFE_PENALTY", 0.75),
        non_production_penalty_floor=_env_float("SCORE_COMPONENT_FLOOR_NON_PRODUCTION_PENALTY", 0.0),
        non_production_penalty_cap=_env_float("SCORE_COMPONENT_CAP_NON_PRODUCTION_PENALTY", 1.0),
    )
    validate_score_component_bounds(bounds)
    return bounds


def _apply_bounds(value: float, floor: float, cap: float) -> float:
    return max(floor, min(cap, value))


def apply_score_component_bounds(
    components: ScoreComponents,
    bounds: ScoreComponentBounds | None = None,
) -> ScoreComponents:
    active_bounds = bounds or load_score_component_bounds()
    validate_score_component_bounds(active_bounds)
    return ScoreComponents(
        quality=round(_apply_bounds(components.quality, active_bounds.quality_floor, active_bounds.quality_cap), 6),
        novelty=round(_apply_bounds(components.novelty, active_bounds.novelty_floor, active_bounds.novelty_cap), 6),
        feasibility=round(
            _apply_bounds(components.feasibility, active_bounds.feasibility_floor, active_bounds.feasibility_cap), 6
        ),
        criteria=round(_apply_bounds(components.criteria, active_bounds.criteria_floor, active_bounds.criteria_cap), 6),
        similarity_penalty=round(
            _apply_bounds(
                components.similarity_penalty,
                active_bounds.similarity_penalty_floor,
                active_bounds.similarity_penalty_cap,
            ),
            6,
        ),
        too_safe_penalty=round(
            _apply_bounds(
                components.too_safe_penalty,
                active_bounds.too_safe_penalty_floor,
                active_bounds.too_safe_penalty_cap,
            ),
            6,
        ),
        non_production_penalty=round(
            _apply_bounds(
                components.non_production_penalty,
                active_bounds.non_production_penalty_floor,
                active_bounds.non_production_penalty_cap,
            ),
            6,
        ),
    )


def compose_final_score(
    components: ScoreComponents,
    weights: ActiveWeightsSnapshot,
    bounds: ScoreComponentBounds | None = None,
) -> FinalScoreBreakdown:
    bounded_components = apply_score_component_bounds(components, bounds=bounds)
    weighted_positive = (
        bounded_components.quality * weights.quality
        + bounded_components.novelty * weights.novelty
        + bounded_components.feasibility * weights.feasibility
        + bounded_components.criteria * weights.criteria
    )
    weighted_penalties = (
        bounded_components.similarity_penalty * weights.similarity_penalty
        + bounded_components.too_safe_penalty * weights.too_safe_penalty
        + bounded_components.non_production_penalty * weights.non_production_penalty
    )
    final_score = weighted_positive - weighted_penalties
    return FinalScoreBreakdown(
        weighted_positive=weighted_positive,
        weighted_penalties=weighted_penalties,
        final_score=round(final_score, 6),
        components=bounded_components,
        weights=weights,
    )
