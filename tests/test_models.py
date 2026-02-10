"""Tests for model dataclasses: to_dict/from_dict round-trips."""
import uuid
import time
from why_combinator.models import AgentEntity, SimulationEntity, InteractionLog, MetricSnapshot, SimulationRun, StakeholderType, SimulationStage


def test_agent_entity_roundtrip():
    agent = AgentEntity(id="a1", type=StakeholderType.CUSTOMER, role="Tester", personality={"k": 0.5}, knowledge_base=["x"], behavior_rules=["y"], name="Test Agent")
    d = agent.to_dict()
    restored = AgentEntity.from_dict(d)
    assert restored.id == agent.id
    assert restored.type == agent.type
    assert restored.role == agent.role
    assert restored.personality == agent.personality
    assert restored.name == agent.name


def test_simulation_entity_roundtrip():
    sim = SimulationEntity(id="s1", name="Test", description="desc", industry="SaaS", stage=SimulationStage.MVP, parameters={"k": 1}, created_at=time.time())
    d = sim.to_dict()
    restored = SimulationEntity.from_dict(d)
    assert restored.id == sim.id
    assert restored.stage == sim.stage
    assert restored.parameters == sim.parameters


def test_interaction_log_roundtrip():
    log = InteractionLog(agent_id="a1", simulation_id="s1", timestamp=time.time(), action="buy", target="startup", outcome={"amount": 100})
    d = log.to_dict()
    restored = InteractionLog(**d)
    assert restored.agent_id == log.agent_id
    assert restored.action == log.action
    assert restored.outcome == log.outcome


def test_metric_snapshot_roundtrip():
    snap = MetricSnapshot(simulation_id="s1", timestamp=time.time(), metric_type="adoption_rate", value=0.42)
    d = snap.to_dict()
    restored = MetricSnapshot(**d)
    assert restored.metric_type == snap.metric_type
    assert restored.value == snap.value


def test_simulation_run_roundtrip():
    run = SimulationRun(simulation_id="s1", start_time=time.time(), duration=100.0, status="completed", results={"score": 85})
    d = run.to_dict()
    assert d["simulation_id"] == "s1"
    assert d["status"] == "completed"
