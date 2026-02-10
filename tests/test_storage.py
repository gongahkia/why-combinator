"""Tests for TinyDBStorageManager CRUD operations."""
import time
from why_combinator.models import AgentEntity, InteractionLog, MetricSnapshot, StakeholderType


def test_create_and_get_simulation(mock_storage, sample_simulation):
    sim = sample_simulation()
    mock_storage.create_simulation(sim)
    retrieved = mock_storage.get_simulation(sim.id)
    assert retrieved is not None
    assert retrieved.name == sim.name
    assert retrieved.industry == sim.industry


def test_list_simulations(mock_storage, sample_simulation):
    sim1 = sample_simulation(name="Sim A")
    sim2 = sample_simulation(name="Sim B")
    mock_storage.create_simulation(sim1)
    mock_storage.create_simulation(sim2)
    sims = mock_storage.list_simulations()
    assert len(sims) == 2
    names = {s.name for s in sims}
    assert "Sim A" in names
    assert "Sim B" in names


def test_save_and_get_agents(mock_storage, sample_simulation, sample_agents):
    sim = sample_simulation()
    mock_storage.create_simulation(sim)
    for agent in sample_agents:
        mock_storage.save_agent(sim.id, agent)
    retrieved = mock_storage.get_agents(sim.id)
    assert len(retrieved) == len(sample_agents)


def test_log_and_get_interactions(mock_storage, sample_simulation):
    sim = sample_simulation()
    mock_storage.create_simulation(sim)
    log = InteractionLog(agent_id="a1", simulation_id=sim.id, timestamp=time.time(), action="buy", target="startup", outcome={"amount": 100})
    mock_storage.log_interaction(log)
    interactions = mock_storage.get_interactions(sim.id)
    assert len(interactions) == 1
    assert interactions[0].action == "buy"


def test_log_and_get_metrics(mock_storage, sample_simulation):
    sim = sample_simulation()
    mock_storage.create_simulation(sim)
    metric = MetricSnapshot(simulation_id=sim.id, timestamp=time.time(), metric_type="adoption_rate", value=0.42)
    mock_storage.log_metric(metric)
    metrics = mock_storage.get_metrics(sim.id)
    assert len(metrics) == 1
    assert metrics[0].value == 0.42


def test_get_nonexistent_simulation(mock_storage):
    assert mock_storage.get_simulation("nonexistent") is None
