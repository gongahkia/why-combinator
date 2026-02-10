from typing import Dict, Any

from why_combinator.models import AgentEntity
from why_combinator.agent.base import BaseAgent
from why_combinator.agent.impl import GenericAgent
from why_combinator.events import EventBus
from why_combinator.llm.base import LLMProvider

def create_agent_instance(entity: AgentEntity, event_bus: EventBus, llm_provider: LLMProvider, world_context: Dict[str, Any]) -> BaseAgent:
    """
    Factory to create a runtime agent instance from an entity description.
    For MVP, we map everything to GenericAgent.
    Future extensions can Map specific Roles to specific sub-classes.
    """
    # For now, all agents use the GenericAgent implementation
    return GenericAgent(
        entity=entity,
        event_bus=event_bus,
        llm_provider=llm_provider,
        world_context=world_context
    )
