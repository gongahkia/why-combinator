from __future__ import annotations

from app.integrations.why_combinator_bridge import (
    infer_startup_industry,
    map_challenge_to_why_parameters,
)


def test_infer_startup_industry_prefers_keyword_match() -> None:
    assert infer_startup_industry("Build a payment fraud detector for retail banking APIs.") == "fintech"
    assert infer_startup_industry("Create a buyer-seller listing and checkout flow.") == "marketplace"
    assert infer_startup_industry("Design an IoT sensor device with remote firmware update.") == "hardware"


def test_infer_startup_industry_defaults_to_saas() -> None:
    assert infer_startup_industry("General productivity assistant for incident workflows.") == "saas"


def test_map_challenge_to_why_parameters_returns_expected_ranges() -> None:
    params = map_challenge_to_why_parameters(
        complexity_slider=0.65,
        minimum_quality_threshold=0.4,
        risk_appetite="aggressive",
        iteration_window_seconds=5400,
    )

    assert params["competitor_count"] == 3
    assert params["revenue_model"] == "subscription"
    assert 0.0 < float(params["conversion_rate"]) < 1.0
    assert float(params["initial_capital"]) > 0
    assert float(params["tam"]) > 10_000
