"""Tests for GenericAgent: perceive/reason/act with MockProvider."""
from why_combinator.agent.impl import GenericAgent
from why_combinator.models import AgentEntity, StakeholderType


def test_agent_perceive_reason_act(sample_agents, event_bus, mock_llm):
    entity = sample_agents[0]
    world_context = {"id": "sim1", "name": "Test", "description": "test", "industry": "SaaS", "stage": "mvp"}
    agent = GenericAgent(entity, event_bus, mock_llm, world_context)

    world_state = {"date": "2025-01-01", "timestamp": 1000.0, "agents": [{"id": entity.id, "name": entity.name, "role": entity.role, "type": entity.type.value}]}
    interaction = agent.run_step(world_state, 1000.0)

    assert interaction is not None
    assert interaction.agent_id == entity.id
    assert interaction.action != ""


def test_agent_produces_interaction_log(sample_agents, event_bus, mock_llm):
    entity = sample_agents[1]  # investor
    world_context = {"id": "sim1", "name": "Test", "description": "test", "industry": "SaaS", "stage": "mvp"}
    agent = GenericAgent(entity, event_bus, mock_llm, world_context)

    world_state = {"date": "2025-01-01", "timestamp": 1000.0, "agents": []}
    interaction = agent.run_step(world_state, 1000.0)

    assert interaction is not None
    assert interaction.simulation_id == "sim1"


def test_agent_memory_updated(sample_agents, event_bus, mock_llm):
    entity = sample_agents[0]
    world_context = {"id": "sim1", "name": "Test", "description": "test", "industry": "SaaS", "stage": "mvp"}
    agent = GenericAgent(entity, event_bus, mock_llm, world_context)

    world_state = {"date": "2025-01-01", "timestamp": 1000.0, "agents": []}
    agent.run_step(world_state, 1000.0)

    assert len(agent.memory) > 0
    assert any("Thought" in m["content"] for m in agent.memory)
