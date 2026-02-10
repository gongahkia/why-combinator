"""Tests for analytics: compare_simulations, risk_assessment, pattern_recognition."""
import time
from why_combinator.models import InteractionLog, MetricSnapshot
from why_combinator.analytics import compare_simulations, risk_assessment, CustomMetricBuilder
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
