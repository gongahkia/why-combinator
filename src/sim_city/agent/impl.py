from typing import Dict, Any, Optional
import logging
import json

from sim_city.models import AgentEntity, InteractionLog
from sim_city.events import EventBus
from sim_city.agent.base import BaseAgent
from sim_city.llm.base import LLMProvider
from sim_city.agent.prompts import (
    SIMULATION_CONTEXT,
    AGENT_IDENTITY,
    DECISION_PROMPT,
    PromptTemplate
)
from sim_city.utils.parsing import extract_json

logger = logging.getLogger(__name__)


class GenericAgent(BaseAgent):
    """
    A generic agent implementation that uses an LLM to decide on actions.
    The behavior is determined by the AgentEntity's role, type, and prompts.
    """

    def __init__(self, entity: AgentEntity, event_bus: EventBus, llm_provider: LLMProvider, 
                 world_context: Dict[str, Any]):
        super().__init__(entity, event_bus)
        self.llm_provider = llm_provider
        # World context includes static info about the simulation (industry, stage, etc)
        self.world_context = world_context

    def perceive(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter world state for relevant information.
        For MVP, we just pass the events or state relevant to the agent.
        """
        # simplified: return the whole state description or recent events
        return world_state

    def reason(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        Construct prompt and query LLM.
        """
        # 1. Build Context Strings
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

        # 2. Build Prompt
        prompt = DECISION_PROMPT.format(
            world_state=json.dumps(perception, indent=2),
            memory=self.get_recent_memories(limit=5),
            personality_summary=f"Be {self.entity.personality.get('dominant_trait', 'consistent')}."
        )

        full_prompt = f"{sim_context_str}\n{identity_str}\n{prompt}"
        
        # 3. Query LLM
        # System prompt could be the identity part
        response_text = self.llm_provider.completion(
            prompt=full_prompt,
            system_prompt="You are a role-playing agent in a business simulation."
        )
        
        # 4. Parse Response
        decision = extract_json(response_text)
        if not decision:
            logger.warning(f"Agent {self.entity.id} produced invalid JSON response: {response_text[:100]}...")
            # Fallback action
            decision = {
                "thought_process": "I am confused and will do nothing.",
                "action_type": "wait",
                "action_details": {}
            }
            
        # Log thought process to memory
        self.add_memory(f"Thought: {decision.get('thought_process', '')}", role="internal")
        
        return decision

    def act(self, decision: Dict[str, Any]) -> InteractionLog:
        """
        Execute the decision.
        """
        action_type = decision.get("action_type", "wait")
        details = decision.get("action_details", {})
        
        # Create interaction log
        # Timestamp will be filled by BaseAgent.run_step
        log = InteractionLog(
            agent_id=self.entity.id,
            simulation_id=self.world_context.get("id", ""),
            timestamp=0.0,
            action=action_type,
            target=details.get("target", "system"),
            outcome=details
        )
        
        return log
