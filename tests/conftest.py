"""Shared pytest fixtures for Why-Combinator tests."""
import pytest
import uuid
import time
import tempfile
from pathlib import Path
from why_combinator.models import AgentEntity, SimulationEntity, InteractionLog, MetricSnapshot, StakeholderType, SimulationStage
from why_combinator.storage import TinyDBStorageManager
from why_combinator.llm.mock import MockProvider
from why_combinator.events import EventBus


@pytest.fixture
def mock_llm():
    """MockProvider instance."""
    return MockProvider()


@pytest.fixture
def event_bus():
    """Fresh EventBus instance."""
    return EventBus()


@pytest.fixture
def mock_storage(tmp_path):
    """TinyDBStorageManager using a temp directory."""
    return TinyDBStorageManager(storage_dir=tmp_path)


@pytest.fixture
def sample_simulation():
    """Factory for SimulationEntity instances."""
    def _factory(**overrides):
        defaults = {
            "id": str(uuid.uuid4()),
            "name": "Test Startup",
            "description": "A test startup simulation",
            "industry": "SaaS",
            "stage": SimulationStage.MVP,
            "parameters": {"market_size": 1000000, "initial_capital": 500000},
            "created_at": time.time(),
        }
        defaults.update(overrides)
        return SimulationEntity(**defaults)
    return _factory


@pytest.fixture
def sample_agents():
    """List of sample AgentEntity instances."""
    return [
        AgentEntity(
            id=str(uuid.uuid4()), type=StakeholderType.CUSTOMER, role="Early Adopter",
            personality={"openness": 0.9, "skepticism": 0.2},
            knowledge_base=["tech trends"], behavior_rules=["Evaluate products"],
            name="Early Adopter (Customer)"
        ),
        AgentEntity(
            id=str(uuid.uuid4()), type=StakeholderType.INVESTOR, role="VC Partner",
            personality={"risk_tolerance": 0.7},
            knowledge_base=["financial modeling"], behavior_rules=["Seek high ROI"],
            name="VC Partner (Investor)"
        ),
        AgentEntity(
            id=str(uuid.uuid4()), type=StakeholderType.COMPETITOR, role="Incumbent",
            personality={"aggression": 0.6},
            knowledge_base=["market defense"], behavior_rules=["Protect market share"],
            name="Incumbent (Competitor)"
        ),
    ]
