from abc import ABC, abstractmethod
from typing import Dict, Any, List

from sim_city.models import AgentEntity, InteractionLog
from sim_city.events import EventBus


class BaseAgent(ABC):
    """Abstract base class for simulation agents."""

    def __init__(self, entity: AgentEntity, event_bus: EventBus):
        self.entity = entity
        self.event_bus = event_bus
        self.memory: List[Dict[str, Any]] = []

    @abstractmethod
    def perceive(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """Gather information from the world."""
        pass

    @abstractmethod
    def reason(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """Process perception and decide on an action."""
        pass

    @abstractmethod
    def act(self, decision: Dict[str, Any]) -> InteractionLog:
        """Execute the decision and produce an outcome."""
        pass

    def run_step(self, world_state: Dict[str, Any], timestamp: float) -> Optional[InteractionLog]:
        """Execute one simulation step for this agent."""
        perception = self.perceive(world_state)
        decision = self.reason(perception)
        interaction = self.act(decision)
        
        if interaction:
             # Fill in the timestamp if not present
            interaction.timestamp = timestamp
            interaction.agent_id = self.entity.id
            self.event_bus.publish("interaction_occurred", interaction.to_dict(), timestamp)
            return interaction
        return None
