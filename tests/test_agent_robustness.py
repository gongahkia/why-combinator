
import pytest
from unittest.mock import MagicMock, AsyncMock
from why_combinator.agent.impl import GenericAgent
from why_combinator.models import AgentEntity, WorldState, StakeholderType
from why_combinator.events import EventBus

@pytest.fixture
def mock_llm_provider():
    provider = MagicMock()
    provider.async_completion = AsyncMock()
    provider.completion = MagicMock()
    return provider

@pytest.fixture
def sample_agent_entity():
    return AgentEntity(
        id="agent-123",
        name="Test Agent",
        role="Tester",
        type=StakeholderType.CUSTOMER,
        personality={},
        knowledge_base=[],
        behavior_rules=[]
    )

@pytest.mark.asyncio
async def test_agent_malformed_json_fallback(mock_llm_provider, sample_agent_entity):
    """Test that agent falls back to 'wait' when LLM returns garbage JSON."""
    
    # Setup agent
    event_bus = EventBus()
    agent = GenericAgent(
        entity=sample_agent_entity,
        event_bus=event_bus,
        llm_provider=mock_llm_provider,
        world_context={"id": "sim-1", "industry": "Tech"}
    )
    
    # Mock LLM to return invalid JSON twice (initial + retry)
    mock_llm_provider.async_completion.side_effect = [
        "I am not a JSON object",
        "{ 'broken': json "
    ]
    
    # Run reason()
    perception = {"date": "2024-01-01"}
    decision = await agent.reason(perception)
    
    # Verify fallback
    assert decision.action_type == "wait" # Not "wait" strictly, likely "wait" or default
    # The code implementation uses "wait" and "thought_process" indicating confusion
    assert "confused" in decision.thought_process.lower()
    
    # Verify LLM was called twice (initial + retry)
    assert mock_llm_provider.async_completion.call_count == 2

def test_agent_perceive_missing_keys(mock_llm_provider, sample_agent_entity):
    """Test perceive handles empty/missing world state keys."""
    event_bus = EventBus()
    agent = GenericAgent(
        entity=sample_agent_entity,
        event_bus=event_bus,
        llm_provider=mock_llm_provider,
        world_context={}
    )
    
    # Empty world state
    empty_state = WorldState(
        id="sim-1",
        tick=1,
        date="2024-01-01",
        timestamp=1000.0,
        stage="idea",
        metrics={}, # Empty metrics
        agents=[],  # Empty agents
        sentiments={},
        relationships={},
        emergence_events=[],
        active_events=[]
    )
    
    # Should not raise KeyError
    perception = agent.perceive(empty_state)
    
    assert perception["date"] == "2024-01-01"
    assert perception["agents"] == []
    assert perception.get("startup_kpis") is None or perception["startup_kpis"] == {} # depending on impl
    
    # Verify accessing missing specific metrics doesn't crash 
    # The implementation checks: if world_state.metrics: ...
    # So if metrics is {}, it skips the kpi block.
    assert "startup_kpis" not in perception

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", __file__]))
