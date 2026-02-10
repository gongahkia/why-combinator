"""Tests for analytics: compare_simulations, risk_assessment, pattern_recognition."""
import time
from why_combinator.models import InteractionLog, MetricSnapshot, ExperimentConfig, SimulationStage, MarketParams, UnitEconomics, FundingState
from why_combinator.analytics import compare_simulations, risk_assessment, CustomMetricBuilder, diff_experiments, aggregate_simulation_batch
from why_combinator.analytics_advanced import pattern_recognition


def test_compare_simulations(mock_storage, sample_simulation):
    sim1 = sample_simulation(name="Alpha")
    sim2 = sample_simulation(name="Beta")
    mock_storage.create_simulation(sim1)
    mock_storage.create_simulation(sim2)
    # Add metrics
    mock_storage.log_metric(MetricSnapshot(simulation_id=sim1.id, timestamp=time.time(), metric_type="adoption_rate", value=0.3))
    mock_storage.log_metric(MetricSnapshot(simulation_id=sim2.id, timestamp=time.time(), metric_type="adoption_rate", value=0.5))
    result = compare_simulations(mock_storage, [sim1.id, sim2.id])
    assert len(result["simulations"]) == 2
    assert "adoption_rate" in result["metric_comparison"]


def test_risk_assessment(mock_storage, sample_simulation):
    sim = sample_simulation()
    mock_storage.create_simulation(sim)
    # Add lots of complaints
    for i in range(10):
        mock_storage.log_interaction(InteractionLog(agent_id=f"a{i}", simulation_id=sim.id, timestamp=time.time(), action="complain", target="startup", outcome={}))
    for i in range(5):
        mock_storage.log_interaction(InteractionLog(agent_id=f"b{i}", simulation_id=sim.id, timestamp=time.time(), action="buy", target="startup", outcome={}))
    risks = risk_assessment(mock_storage, sim.id)
    assert len(risks) > 0
    assert any("dissatisfaction" in r["risk"].lower() for r in risks)


def test_pattern_recognition_with_interactions():
    interactions = [
        InteractionLog(agent_id="a1", simulation_id="s1", timestamp=1.0, action="buy", target="x", outcome={}),
        InteractionLog(agent_id="a2", simulation_id="s1", timestamp=2.0, action="invest", target="x", outcome={}),
        InteractionLog(agent_id="a3", simulation_id="s1", timestamp=3.0, action="complain", target="x", outcome={}),
    ]
    patterns = pattern_recognition(interactions)
    assert "success_indicators" in patterns
    assert "failure_indicators" in patterns


def test_custom_metric_builder_safe_eval():
    builder = CustomMetricBuilder()
    builder.define("ratio", "adoption_rate / churn_rate")
    builder.define("score", "adoption_rate * 100 + market_share * 50")
    metrics = {"adoption_rate": 0.5, "churn_rate": 0.1, "market_share": 0.2}
    assert builder.calculate("ratio", metrics) == 5.0
    assert builder.calculate("score", metrics) == 60.0


def test_custom_metric_builder_division_by_zero():
    builder = CustomMetricBuilder()
    builder.define("bad", "adoption_rate / churn_rate")
    result = builder.calculate("bad", {"adoption_rate": 0.5, "churn_rate": 0.0})
    assert result == 0.0


def test_custom_metric_builder_rejects_builtins():
    builder = CustomMetricBuilder()
    builder.define("hack", "__import__('os').system('echo pwned')")
    result = builder.calculate("hack", {"adoption_rate": 0.5})
    assert result == 0.0


def test_experiment_config_diff():
    """Test diff_experiments correctly identifies changes."""
    # Base config
    base = ExperimentConfig(
        simulation_name="Exp1", industry="Tech", stage=SimulationStage.MVP,
        agent_count=10, 
        market_params=MarketParams(tam=1000.0),
        unit_economics=UnitEconomics(cac=10, gross_margin=0.5, opex_ratio=0.2, base_opex=1000, price_per_unit=100),
        funding_state=FundingState(initial_capital=5000),
        llm_model="mock"
    )
    
    # Modified config
    modified = ExperimentConfig(
        simulation_name="Exp2", industry="Tech", stage=SimulationStage.MVP,
        agent_count=10,
        market_params=MarketParams(tam=2000.0), # Changed TAM
        unit_economics=UnitEconomics(cac=10, gross_margin=0.5, opex_ratio=0.2, base_opex=1000, price_per_unit=100),
        funding_state=FundingState(initial_capital=5000),
        llm_model="mock"
    )
    
    diff = diff_experiments(base, modified)
    
    # Verify name change
    assert "simulation_name" in diff
    assert diff["simulation_name"]["old"] == "Exp1"
    assert diff["simulation_name"]["new"] == "Exp2"
    
    # Verify nested diff in market_params
    assert "market_params" in diff
    # Depending on diff implementation, it might show the whole dict or nested diff
    # The diff_experiments function recurses for dicts, but dataclasses to_dict returns dicts.
    # So it should be nested.
    assert "tam" in diff["market_params"]
    assert diff["market_params"]["tam"]["old"] == 1000.0
    assert diff["market_params"]["tam"]["new"] == 2000.0
    
    # Verify unchanged fields not in diff
    assert "agent_count" not in diff


def test_cross_simulation_aggregation(mock_storage, sample_simulation):
    """Test aggregate_simulation_batch returns correct stats."""
    
    # Create 3 simulations with prefix "BatchTest"
    sims = []
    for i, val in enumerate([10.0, 20.0, 30.0]):
        s = sample_simulation(name=f"BatchTest-{i}")
        mock_storage.create_simulation(s)
        mock_storage.log_metric(MetricSnapshot(
            simulation_id=s.id, timestamp=time.time(), 
            metric_type="adoption_rate", value=val
        ))
        sims.append(s)
        
    # Aggregate
    results = aggregate_simulation_batch(mock_storage, experiment_name_prefix="BatchTest")
    
    assert "adoption_rate" in results
    stats = results["adoption_rate"]
    
    assert stats["count"] == 3
    assert stats["min"] == 10.0
    assert stats["max"] == 30.0
    assert stats["mean"] == 20.0
    assert stats["p50"] == 20.0
    # stddev of 10, 20, 30 is 10.0
    # variance = ((10-20)^2 + (20-20)^2 + (30-20)^2) / 2 = (100+0+100)/2 = 100. sqrt(100)=10.
    assert abs(stats["stddev"] - 10.0) < 0.001

if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main(["-v", __file__]))
