from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.analytics import MarketSimulationRequest, get_market_simulation_metrics
from app.db.enums import RunState
from app.db.models import Challenge, Run
from app.integrations.why_combinator_bridge import WhyCombinatorSimulationResult


@pytest.mark.asyncio
async def test_market_simulation_endpoint_uses_bridge_and_returns_mapped_response(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenge = Challenge(
        title="Market simulation hook",
        prompt="Build a payment risk engine for card issuing APIs.",
        iteration_window_seconds=3600,
        minimum_quality_threshold=0.35,
        risk_appetite="balanced",
        complexity_slider=0.6,
    )
    session.add(challenge)
    await session.flush()

    run = Run(
        challenge_id=challenge.id,
        state=RunState.RUNNING,
        started_at=datetime(2026, 2, 28, 0, 0, tzinfo=UTC),
        config_snapshot={"reproducibility": {"run_seed": 123456}},
    )
    session.add(run)
    await session.commit()

    captured = {}

    def _fake_simulation_runner(request):
        captured["request"] = request
        return WhyCombinatorSimulationResult(
            simulation_id="sim-123",
            summary={
                "recommendation": "Promising trajectory",
                "strengths": ["Strong early adoption signals"],
                "weaknesses": ["Burn rate may be unsustainable"],
            },
            latest_metrics={"adoption_rate": 0.24, "runway_months": 9.1},
        )

    monkeypatch.setattr(
        "app.api.analytics.run_why_combinator_market_simulation",
        _fake_simulation_runner,
    )

    response = await get_market_simulation_metrics(
        run.id,
        payload=MarketSimulationRequest(duration_ticks=25, model="mock", speed_multiplier=500.0),
        session=session,
    )

    assert response.run_id == run.id
    assert response.simulation_id == "sim-123"
    assert response.industry == "fintech"
    assert response.seed == 123456
    assert response.recommendation == "Promising trajectory"
    assert response.latest_metrics["runway_months"] == pytest.approx(9.1, abs=1e-6)
    assert captured["request"].duration_ticks == 25
    assert captured["request"].model == "mock"


@pytest.mark.asyncio
async def test_market_simulation_endpoint_returns_not_found_for_unknown_run(
    session: AsyncSession,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_market_simulation_metrics(
            run_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            payload=MarketSimulationRequest(),
            session=session,
        )

    assert exc_info.value.status_code == 404
