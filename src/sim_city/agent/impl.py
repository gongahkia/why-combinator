from typing import Dict, Any, Optional
import logging
import json
from sim_city.models import AgentEntity, InteractionLog
from sim_city.events import EventBus
from sim_city.agent.base import BaseAgent
from sim_city.llm.base import LLMProvider
from sim_city.agent.prompts import SIMULATION_CONTEXT, AGENT_IDENTITY, DECISION_PROMPT, PromptTemplate
from sim_city.utils.parsing import extract_json

logger = logging.getLogger(__name__)

class GenericAgent(BaseAgent):
    """Generic LLM-driven agent. Behavior determined by entity role/type/prompts."""
    def __init__(self, entity: AgentEntity, event_bus: EventBus, llm_provider: LLMProvider, world_context: Dict[str, Any]):
        super().__init__(entity, event_bus)
        self.llm_provider = llm_provider
        self.world_context = world_context
    def perceive(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        perception = dict(world_state)
        messages = self.get_pending_messages()
        if messages:
            perception["incoming_messages"] = [{"from": m.get("sender_name", "?"), "content": m.get("content", "")} for m in messages]
        return perception
    def reason(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        sim_context_str = SIMULATION_CONTEXT.format(
            industry=self.world_context.get("industry", "Unknown"),
            stage=self.world_context.get("stage", "Unknown"),
            startup_name=self.world_context.get("name", "Unknown Startup"),
            startup_description=self.world_context.get("description", ""),
            date=perception.get("date", "Unknown Date")
        )
        identity_str = AGENT_IDENTITY.format(
            name=self.entity.name,
            role=self.entity.role,
            type=self.entity.type.value,
            personality=json.dumps(self.entity.personality, indent=2),
            knowledge_base=json.dumps(self.entity.knowledge_base, indent=2),
            behavior_rules=json.dumps(self.entity.behavior_rules, indent=2)
        )
        prompt = DECISION_PROMPT.format(
            world_state=json.dumps(perception, indent=2),
            memory=self.get_recent_memories(limit=5),
            personality_summary=f"Be {self.entity.personality.get('dominant_trait', 'consistent')}."
        )
        goals_str = f"\nYOUR GOALS:\n{self.get_goals_summary()}\n" if self.goals else ""
        strategy_str = f"\nYOUR STRATEGY: {self.strategy}\n" if self.strategy else ""
        full_prompt = f"{sim_context_str}\n{identity_str}{goals_str}{strategy_str}\n{prompt}"
        response_text = self.llm_provider.completion(prompt=full_prompt, system_prompt="You are a role-playing agent in a business simulation.")
        decision = extract_json(response_text)
        if not decision:
            logger.warning(f"Agent {self.entity.id} produced invalid JSON: {response_text[:100]}...")
            decision = {"thought_process": "I am confused and will do nothing.", "action_type": "wait", "action_details": {}}
        self.add_memory(f"Thought: {decision.get('thought_process', '')}", role="internal")
        if decision.get("new_goal"): # LLM can set goals
            self.set_goal(decision["new_goal"], priority=decision.get("goal_priority", 0.5))
        if decision.get("strategy_update"): # LLM can update strategy
            self.set_strategy(decision["strategy_update"])
        return decision
    def act(self, decision: Dict[str, Any]) -> InteractionLog:
        action_type = decision.get("action_type", "wait")
        details = decision.get("action_details", {})
        if action_type == "send_message" and details.get("target_agent_id"): # inter-agent comm
            self.send_message(details["target_agent_id"], details.get("content", ""), timestamp=0.0)
        log = InteractionLog(
            agent_id=self.entity.id,
            simulation_id=self.world_context.get("id", ""),
            timestamp=0.0,
            action=action_type,
            target=details.get("target", "system"),
            outcome=details
        )
        return log
