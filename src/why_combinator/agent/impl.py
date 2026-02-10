from typing import Dict, Any, Optional, List
import logging
import json
from why_combinator.models import AgentEntity, InteractionLog, WorldState, InteractionOutcome
from why_combinator.events import EventBus
from why_combinator.agent.base import BaseAgent
from why_combinator.llm.base import LLMProvider
from why_combinator.agent.prompts import SIMULATION_CONTEXT, AGENT_IDENTITY, DECISION_PROMPT, MEMORY_SUMMARIZATION_PROMPT, PromptTemplate
from why_combinator.utils.parsing import extract_json

logger = logging.getLogger(__name__)

class GenericAgent(BaseAgent):
    """Generic LLM-driven agent. Behavior determined by entity role/type/prompts."""
    def __init__(self, entity: AgentEntity, event_bus: EventBus, llm_provider: LLMProvider, world_context: Dict[str, Any], max_memory_size: int = 100, max_inbox_size: int = 50):
        super().__init__(entity, event_bus, max_memory_size, max_inbox_size)
        self.llm_provider = llm_provider
        self.world_context = world_context
        
        # Add basic invariants
        self.add_invariant("role_integrity", self._check_role_integrity)
        
        
    def _check_role_integrity(self, interaction: InteractionLog, world_state: WorldState) -> bool:
        """Ensure actions are consistent with agent role."""
        action = interaction.action.lower()
        role = self.entity.type.value
        
        # Restricted actions
        if action == "invest" and role != "investor":
            return False
        if action == "regulate" and role != "regulator":
            return False
        if action == "code" and role != "employee":
            return False
            
        return True
    
    def _create_memory_summary(self, memories: List[Dict[str, Any]]) -> str:
        """Use LLM to create intelligent memory summary."""
        # Format memories for summarization
        memory_text = "\n".join(
            f"[{m.get('role', 'unknown')}] {m.get('content', '')}" 
            for m in memories
        )
        
        prompt = MEMORY_SUMMARIZATION_PROMPT.format(
            count=len(memories),
            memories=memory_text
        )
        
        # Use sync completion (this is called during memory management, not in main loop)
        try:
            summary = self.llm_provider.completion(prompt, system_prompt="You are a memory summarization assistant.")
            return summary.strip() if summary else super()._create_memory_summary(memories)
        except Exception as e:
            logger.warning(f"LLM summarization failed: {e}, using rule-based fallback")
            return super()._create_memory_summary(memories)
    
    def perceive(self, world_state: WorldState) -> Dict[str, Any]:
        perception = dict(world_state.metrics) if world_state.metrics else {}
        perception["date"] = world_state.date
        perception["stage"] = world_state.stage
        perception["agents"] = world_state.agents
        perception["sentiments"] = world_state.sentiments
        messages = self.get_pending_messages()
        if messages:
            perception["incoming_messages"] = [{"from": m.get("sender_name", "?"), "content": m.get("content", "")} for m in messages]
        # Inject emergence flags and active events for agent awareness
        if world_state.emergence_events:
            perception["emergence_flags"] = world_state.emergence_events[-3:]
        if world_state.active_events:
            perception["active_event"] = world_state.active_events
            
        # Inject Key Performance Indicators (KPIs) for economic awareness
        if world_state.metrics:
            m = world_state.metrics
            perception["startup_kpis"] = {
                "runway_months": m.get("runway_months", "Unknown"),
                "monthly_burn": m.get("burn_rate", "Unknown"),
                "cumulative_revenue": m.get("revenue", "Unknown"),
                "adoption_p_all": m.get("adoption_rate", "Unknown"),
                "churn_rate": m.get("churn_rate", "Unknown"),
                "market_share": m.get("market_share", "Unknown"),
                "product_quality": m.get("product_quality", "Unknown")
            }
        return perception
    async def reason(self, perception: Dict[str, Any]) -> InteractionOutcome:
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
        difficulty_str = ""
        if self.difficulty > 2.0:
            difficulty_str = "\nYou are a veteran in this market. Think multiple moves ahead, consider game theory, and exploit market inefficiencies.\n"
        elif self.difficulty > 1.5:
            difficulty_str = "\nYou are now more experienced and sophisticated. Be more strategic, consider second-order effects, and make nuanced decisions.\n"
        # Inject relationship context
        relationship_str = ""
        agents_data = perception.get("agents", [])
        agent_id_to_name = {a.get("id", ""): a.get("name", "?") for a in agents_data}
        sentiments = perception.get("sentiments", {})
        my_sentiment = sentiments.get(self.entity.id, 0.0)
        # Sentiment trend
        sentiment_str = ""
        if sentiments:
            if my_sentiment > 0.2:
                sentiment_str = "\nMARKET SENTIMENT: The market feels POSITIVE about this startup (rising confidence).\n"
            elif my_sentiment < -0.2:
                sentiment_str = "\nMARKET SENTIMENT: The market feels NEGATIVE about this startup (falling confidence).\n"
            else:
                sentiment_str = "\nMARKET SENTIMENT: The market sentiment is NEUTRAL/STABLE.\n"
        full_prompt = f"{sim_context_str}\n{identity_str}{goals_str}{strategy_str}{difficulty_str}{sentiment_str}\n{prompt}"
        response_text = await self.llm_provider.async_completion(prompt=full_prompt, system_prompt="You are a role-playing agent in a business simulation.")
        decision = extract_json(response_text)
        if not decision:
            logger.warning(f"Agent {self.entity.id} produced invalid JSON: {response_text[:100]}...")
            decision = {"thought_process": "I am confused and will do nothing.", "action_type": "wait", "action_details": {}}
        self.add_memory(f"Thought: {decision.get('thought_process', '')}", role="internal")
        if decision.get("new_goal"): # LLM can set goals
            self.set_goal(decision["new_goal"], priority=decision.get("goal_priority", 0.5))
        if decision.get("strategy_update"): # LLM can update strategy
            self.set_strategy(decision["strategy_update"])
        return InteractionOutcome(
            thought_process=decision.get("thought_process", ""),
            action_type=decision.get("action_type", "wait"),
            target=decision.get("action_details", {}).get("target", "system"),
            details=decision.get("action_details", {}),
            confidence=decision.get("confidence", 1.0)
        )
    def act(self, decision: InteractionOutcome) -> InteractionLog:
        action_type = decision.action_type
        details = decision.details
        if action_type == "send_message" and details.get("target_agent_id"): # inter-agent comm
            self.send_message(details["target_agent_id"], details.get("content", ""), timestamp=0.0)
        log = InteractionLog(
            agent_id=self.entity.id,
            simulation_id=self.world_context.get("id", ""),
            timestamp=0.0,
            action=action_type,
            target=decision.target,
            outcome=details
        )
        return log
