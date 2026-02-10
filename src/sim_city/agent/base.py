from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from sim_city.models import AgentEntity, InteractionLog
from sim_city.events import EventBus


class BaseAgent(ABC):
    """Abstract base class for simulation agents."""
    def __init__(self, entity: AgentEntity, event_bus: EventBus):
        self.entity = entity
        self.event_bus = event_bus
        self.memory: List[Dict[str, Any]] = []
        self.inbox: List[Dict[str, Any]] = [] # inter-agent messages
        self.event_bus.subscribe("agent_message", self._on_message)
    def _on_message(self, event):
        """Receive messages targeted at this agent."""
        if event.payload.get("target_id") == self.entity.id:
            self.inbox.append(event.payload)
            self.add_memory(f"Message from {event.payload.get('sender_name','?')}: {event.payload.get('content','')}", role="message", timestamp=event.timestamp)
    def send_message(self, target_id: str, content: str, timestamp: float = 0.0):
        """Send a message to another agent via event bus."""
        self.event_bus.publish("agent_message", {
            "sender_id": self.entity.id,
            "sender_name": self.entity.name,
            "target_id": target_id,
            "content": content,
        }, timestamp)
    def get_pending_messages(self) -> List[Dict[str, Any]]:
        """Drain and return pending inbox messages."""
        msgs = list(self.inbox)
        self.inbox.clear()
        return msgs
    def add_memory(self, content: str, role: str = "observation", timestamp: float = 0.0):
        self.memory.append({"content": content, "role": role, "timestamp": timestamp})
    def get_recent_memories(self, limit: int = 5) -> str:
        return "\n".join(f"[{m['role']}] {m['content']}" for m in self.memory[-limit:])
    @abstractmethod
    def perceive(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        pass
    @abstractmethod
    def reason(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        pass
    @abstractmethod
    def act(self, decision: Dict[str, Any]) -> InteractionLog:
        pass
    def run_step(self, world_state: Dict[str, Any], timestamp: float) -> Optional[InteractionLog]:
        perception = self.perceive(world_state)
        decision = self.reason(perception)
        interaction = self.act(decision)
        if interaction:
            interaction.timestamp = timestamp
            interaction.agent_id = self.entity.id
            self.event_bus.publish("interaction_occurred", interaction.to_dict(), timestamp)
            return interaction
        return None
