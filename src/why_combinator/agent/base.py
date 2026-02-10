from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Tuple
import logging
import asyncio

logger = logging.getLogger(__name__)

from why_combinator.models import AgentEntity, InteractionLog, WorldState, InteractionOutcome
from why_combinator.events import EventBus


class BaseAgent(ABC):
    """Abstract base class for simulation agents."""
    def __init__(self, entity: AgentEntity, event_bus: EventBus, max_memory_size: int = 100, max_inbox_size: int = 50):
        self.entity = entity
        self.event_bus = event_bus
        self.memory: List[Dict[str, Any]] = []
        self.inbox: List[Dict[str, Any]] = [] # inter-agent messages
        self.goals: List[Dict[str, Any]] = [] # agent goals: [{goal, priority, progress}]
        self.strategy: str = "" # current high-level strategy
        self.difficulty: float = 1.0 # 1.0=baseline, increases over time
        self.difficulty: float = 1.0 # 1.0=baseline, increases over time
        self._steps_taken: int = 0
        self._invariants: List[Tuple[str, Callable[[InteractionLog, WorldState], bool]]] = [] 
        self._max_memory_size = max_memory_size
        self._max_inbox_size = max_inbox_size
        self.event_bus.subscribe("agent_message", self._on_message)
        
    def add_invariant(self, name: str, check: Callable[[InteractionLog, WorldState], bool]):
        """Register an invariant check. Raises exception if check returns False."""
        self._invariants.append((name, check))
    def _on_message(self, event):
        """Receive messages targeted at this agent."""
        if event.payload.get("target_id") == self.entity.id:
            # Apply inbox cap: drop oldest if exceeded
            if len(self.inbox) >= self._max_inbox_size:
                dropped = self.inbox.pop(0)
                logger.warning(f"Agent {self.entity.id} inbox full ({self._max_inbox_size}), dropped message from {dropped.get('sender_name', '?')}")
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
        # Check if memory eviction is needed
        if len(self.memory) > self._max_memory_size:
            self._evict_and_summarize_memory()
    
    def _evict_and_summarize_memory(self):
        """Evict oldest memories and create summary when max size exceeded."""
        # Calculate how many to evict (evict 30% when threshold hit)
        evict_count = max(1, int(self._max_memory_size * 0.3))
        to_summarize = self.memory[:evict_count]
        
        # Create summary of evicted memories
        if to_summarize:
            summary_text = self._create_memory_summary(to_summarize)
            summary_entry = {
                "content": f"[SUMMARY of {evict_count} old memories] {summary_text}",
                "role": "summary",
                "timestamp": to_summarize[-1].get("timestamp", 0.0)
            }
            # Remove old memories and prepend summary
            self.memory = [summary_entry] + self.memory[evict_count:]
            logger.debug(f"Agent {self.entity.id} evicted {evict_count} memories, created summary")
    
    def _create_memory_summary(self, memories: List[Dict[str, Any]]) -> str:
        """Create a text summary of memories. Can be overridden for LLM-based summarization."""
        # Simple rule-based summarization (subclasses can override for LLM)
        roles = {}
        for m in memories:
            role = m.get("role", "other")
            if role not in roles:
                roles[role] = []
            roles[role].append(m.get("content", "")[:50])
        
        parts = []
        for role, contents in roles.items():
            parts.append(f"{len(contents)} {role} events")
        
        return "; ".join(parts)
    def get_recent_memories(self, limit: int = 5) -> str:
        return "\n".join(f"[{m['role']}] {m['content']}" for m in self.memory[-limit:])
    def set_goal(self, goal: str, priority: float = 0.5):
        self.goals.append({"goal": goal, "priority": priority, "progress": 0.0})
        self.goals.sort(key=lambda g: g["priority"], reverse=True)
    def update_goal_progress(self, goal_idx: int, progress: float):
        if 0 <= goal_idx < len(self.goals):
            self.goals[goal_idx]["progress"] = min(1.0, progress)
    def get_goals_summary(self) -> str:
        if not self.goals:
            return "No explicit goals set."
        return "\n".join(f"- [{g['progress']:.0%}] (P{g['priority']:.1f}) {g['goal']}" for g in self.goals)
    def set_strategy(self, strategy: str):
        self.strategy = strategy
        self.add_memory(f"Strategy updated: {strategy}", role="strategy")
    @abstractmethod
    def perceive(self, world_state: WorldState) -> Dict[str, Any]:
        pass
    @abstractmethod
    async def reason(self, perception: Dict[str, Any]) -> InteractionOutcome:
        pass
    @abstractmethod
    def act(self, decision: InteractionOutcome) -> InteractionLog:
        pass
    async def run_step(self, world_state: WorldState, timestamp: float) -> Optional[InteractionLog]:
        self._steps_taken += 1
        if self._steps_taken % 20 == 0:
            self.difficulty = min(3.0, self.difficulty + 0.1)
        # Memory reflection and eviction check every 10 steps
        if self._steps_taken % 10 == 0 and len(self.memory) >= 5:
            recent = self.memory[-10:]
            actions = [m["content"] for m in recent if m.get("role") == "internal"]
            if actions:
                summary = f"Reflection: Over my last {len(actions)} decisions, my focus has been on {actions[-1][:60] if actions else 'various activities'}."
                self.memory.insert(0, {"content": summary, "role": "reflection", "timestamp": timestamp})
        perception = self.perceive(world_state)
        decision = await self.reason(perception)
        interaction = self.act(decision)
        if interaction:
            # Check invariants
            for name, check in self._invariants:
                if not check(interaction, world_state):
                    error_msg = f"Invariant '{name}' violated by agent {self.entity.id} ({self.entity.role}) on action {interaction.action}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                    
            interaction.timestamp = timestamp
            interaction.agent_id = self.entity.id
            self.event_bus.publish("interaction_occurred", interaction.to_dict(), timestamp)
            return interaction
        return None
