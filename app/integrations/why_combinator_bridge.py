from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


class WhyCombinatorUnavailableError(RuntimeError):
    """Raised when why-combinator cannot be imported or executed."""


@dataclass(frozen=True)
class WhyCombinatorSimulationRequest:
    simulation_name: str
    industry: str
    description: str
    stage: str
    duration_ticks: int
    model: str
    speed_multiplier: float
    seed: int | None
    parameters: dict[str, Any]
    persist_simulation: bool = False
    repo_path: str | None = None
    data_dir: str | None = None


@dataclass(frozen=True)
class WhyCombinatorSimulationResult:
    simulation_id: str
    summary: dict[str, Any]
    latest_metrics: dict[str, float]


def infer_startup_industry(prompt: str) -> str:
    lowered = prompt.lower()
    keyword_map: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("fintech", ("fintech", "bank", "payment", "ledger", "wallet", "loan", "fraud", "kyc")),
        ("marketplace", ("marketplace", "buyer", "seller", "merchant", "supply-demand", "listing")),
        ("hardware", ("hardware", "device", "iot", "sensor", "robot", "chip", "firmware")),
        ("saas", ("saas", "b2b", "workflow", "ticketing", "dashboard", "crm", "automation")),
    )
    for industry, keywords in keyword_map:
        if any(keyword in lowered for keyword in keywords):
            return industry
    return "saas"


def map_challenge_to_why_parameters(
    *,
    complexity_slider: float,
    minimum_quality_threshold: float,
    risk_appetite: str,
    iteration_window_seconds: int,
) -> dict[str, float | int | str]:
    appetite_key = risk_appetite.lower()
    appetite_competitors = {"conservative": 5, "balanced": 4, "aggressive": 3}
    appetite_capital = {"conservative": 350_000.0, "balanced": 500_000.0, "aggressive": 750_000.0}
    appetite_burn_multiplier = {"conservative": 0.9, "balanced": 1.0, "aggressive": 1.25}

    runway_months = max(iteration_window_seconds / 30.0 / 86_400.0, 0.5)
    base_opex = 4_000.0 + (complexity_slider * 6_000.0)
    initial_capital = appetite_capital.get(appetite_key, 500_000.0) * (0.8 + runway_months)

    return {
        "tam": round(12_000.0 + (complexity_slider * 38_000.0), 2),
        "viral_coefficient": round(0.05 + (complexity_slider * 0.18), 4),
        "conversion_rate": round(0.03 + ((1.0 - minimum_quality_threshold) * 0.08), 4),
        "competitor_count": appetite_competitors.get(appetite_key, 4),
        "competitor_quality_avg": round(0.5 + (minimum_quality_threshold * 0.35), 4),
        "retention_half_life": round(140.0 + (minimum_quality_threshold * 160.0), 2),
        "price_per_unit": round(49.0 + (complexity_slider * 200.0), 2),
        "revenue_model": "subscription",
        "cac": round(35.0 + (complexity_slider * 70.0), 2),
        "gross_margin": round(0.62 + (minimum_quality_threshold * 0.25), 4),
        "opex_ratio": round(0.45 + ((1.0 - minimum_quality_threshold) * 0.2), 4),
        "base_opex": round(base_opex * appetite_burn_multiplier.get(appetite_key, 1.0), 2),
        "initial_capital": round(initial_capital, 2),
        "revenue_growth_rate": round(0.04 + (complexity_slider * 0.05), 4),
        "burn_growth_rate": round(0.015 + ((1.0 - minimum_quality_threshold) * 0.04), 4),
    }


def run_why_combinator_market_simulation(
    request: WhyCombinatorSimulationRequest,
) -> WhyCombinatorSimulationResult:
    why_api = _load_why_combinator_api(
        repo_path=request.repo_path,
        data_dir=request.data_dir,
    )
    simulation = why_api.create_simulation(
        name=request.simulation_name,
        industry=request.industry,
        description=request.description,
        stage=request.stage,
        parameters=dict(request.parameters),
    )

    try:
        summary = why_api.run_simulation(
            simulation_id=simulation.id,
            duration=request.duration_ticks,
            model=request.model,
            speed=request.speed_multiplier,
            cache=True,
            seed=request.seed,
            headless=True,
        )
        latest_metrics = _extract_latest_metrics(why_api, simulation.id)
        return WhyCombinatorSimulationResult(
            simulation_id=simulation.id,
            summary=summary,
            latest_metrics=latest_metrics,
        )
    finally:
        if not request.persist_simulation:
            try:
                why_api.delete_simulation(simulation.id)
            except Exception:
                # Best-effort cleanup; simulation data can still be inspected manually.
                pass


def _extract_latest_metrics(why_api: ModuleType, simulation_id: str) -> dict[str, float]:
    storage = why_api._get_storage()
    latest_by_type: dict[str, float] = {}
    for snapshot in storage.get_metrics(simulation_id):
        metric_type = getattr(snapshot, "metric_type", None)
        value = getattr(snapshot, "value", None)
        if isinstance(metric_type, str) and isinstance(value, (int, float)):
            latest_by_type[metric_type] = float(value)
    return latest_by_type


def _load_why_combinator_api(repo_path: str | None, data_dir: str | None) -> ModuleType:
    if data_dir and "WHY_COMBINATOR_DATA_DIR" not in os.environ:
        os.environ["WHY_COMBINATOR_DATA_DIR"] = data_dir

    try:
        return importlib.import_module("why_combinator.api")
    except Exception as first_error:
        _extend_sys_path_for_why_combinator(repo_path)
        try:
            return importlib.import_module("why_combinator.api")
        except Exception as second_error:
            raise WhyCombinatorUnavailableError(
                "why-combinator is unavailable. Install dependencies and set WHY_COMBINATOR_REPO_PATH "
                "or install why-combinator as a package."
            ) from (second_error or first_error)


def _extend_sys_path_for_why_combinator(repo_path: str | None) -> None:
    candidates: list[Path] = []
    if repo_path:
        repo = Path(repo_path).expanduser().resolve()
        candidates.extend([repo, repo / "src"])

    sibling_repo = Path(__file__).resolve().parents[3] / "why-combinator"
    candidates.extend([sibling_repo, sibling_repo / "src"])

    for candidate in candidates:
        candidate_str = str(candidate)
        if candidate.exists() and candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
