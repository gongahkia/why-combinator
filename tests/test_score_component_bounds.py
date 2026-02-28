from __future__ import annotations

import pytest

from app.scoring.final_score import (
    ScoreComponentBounds,
    ScoreComponentBoundsValidationError,
    ScoreComponents,
    apply_score_component_bounds,
    compose_final_score,
    load_score_component_bounds,
)
from app.scoring.weights import DEFAULT_WEIGHTS


def test_compose_final_score_applies_default_penalty_caps() -> None:
    breakdown = compose_final_score(
        ScoreComponents(
            quality=0.9,
            novelty=0.8,
            feasibility=0.7,
            criteria=0.6,
            similarity_penalty=1.0,
            too_safe_penalty=0.95,
            non_production_penalty=1.2,
        ),
        DEFAULT_WEIGHTS,
    )

    assert breakdown.components.similarity_penalty == pytest.approx(0.75, abs=1e-6)
    assert breakdown.components.too_safe_penalty == pytest.approx(0.75, abs=1e-6)
    assert breakdown.components.non_production_penalty == pytest.approx(1.0, abs=1e-6)
    assert breakdown.weighted_penalties == pytest.approx(1.3, abs=1e-6)


def test_apply_score_component_bounds_supports_custom_bounds() -> None:
    custom_bounds = ScoreComponentBounds(
        quality_floor=0.2,
        quality_cap=0.7,
        novelty_floor=0.1,
        novelty_cap=0.8,
        feasibility_floor=0.1,
        feasibility_cap=0.6,
        criteria_floor=0.0,
        criteria_cap=0.5,
        similarity_penalty_floor=0.0,
        similarity_penalty_cap=0.4,
        too_safe_penalty_floor=0.1,
        too_safe_penalty_cap=0.3,
        non_production_penalty_floor=0.2,
        non_production_penalty_cap=0.5,
    )

    bounded = apply_score_component_bounds(
        ScoreComponents(
            quality=0.1,
            novelty=0.9,
            feasibility=0.0,
            criteria=0.9,
            similarity_penalty=0.9,
            too_safe_penalty=0.0,
            non_production_penalty=0.9,
        ),
        custom_bounds,
    )

    assert bounded.quality == pytest.approx(0.2, abs=1e-6)
    assert bounded.novelty == pytest.approx(0.8, abs=1e-6)
    assert bounded.feasibility == pytest.approx(0.1, abs=1e-6)
    assert bounded.criteria == pytest.approx(0.5, abs=1e-6)
    assert bounded.similarity_penalty == pytest.approx(0.4, abs=1e-6)
    assert bounded.too_safe_penalty == pytest.approx(0.1, abs=1e-6)
    assert bounded.non_production_penalty == pytest.approx(0.5, abs=1e-6)


def test_load_score_component_bounds_rejects_invalid_floor_cap_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCORE_COMPONENT_FLOOR_QUALITY", "0.9")
    monkeypatch.setenv("SCORE_COMPONENT_CAP_QUALITY", "0.2")

    with pytest.raises(ScoreComponentBoundsValidationError, match="quality_floor"):
        load_score_component_bounds()


def test_load_score_component_bounds_rejects_non_numeric_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCORE_COMPONENT_CAP_SIMILARITY_PENALTY", "not-a-number")

    with pytest.raises(ScoreComponentBoundsValidationError, match="SCORE_COMPONENT_CAP_SIMILARITY_PENALTY"):
        load_score_component_bounds()
