"""Multi-agent debate system for complex decisions."""
import json
import logging
from typing import List, Dict, Any, Optional
from sim_city.agent.base import BaseAgent
from sim_city.llm.base import LLMProvider
from sim_city.utils.parsing import extract_json

logger = logging.getLogger(__name__)

DEBATE_PROMPT = """You are participating in a multi-stakeholder debate about: {topic}
Context: {context}
Your role: {role} ({agent_type})
Previous arguments:
{history}
Provide your argument as JSON:
{{"position": "for/against/neutral", "argument": "your reasoning", "rebuttal": "response to previous points if any", "confidence": 0.0-1.0}}"""

SYNTHESIS_PROMPT = """Synthesize the following debate into a final decision:
Topic: {topic}
Arguments:
{arguments}
Provide synthesis as JSON:
{{"decision": "the consensus or majority decision", "key_points": ["point1", "point2"], "dissenting_views": ["view1"], "confidence": 0.0-1.0}}"""

class DebateSession:
    """Orchestrates a multi-round debate between agents."""
    def __init__(self, topic: str, context: str, llm_provider: LLMProvider, rounds: int = 3):
        self.topic = topic
        self.context = context
        self.llm = llm_provider
        self.rounds = rounds
        self.history: List[Dict[str, Any]] = []
    def run(self, agents: List[BaseAgent]) -> Dict[str, Any]:
        """Run debate for N rounds, return synthesized result."""
        for round_num in range(self.rounds):
            for agent in agents:
                history_str = "\n".join(f"[{h['agent']}] {h['position']}: {h['argument']}" for h in self.history) or "None yet."
                prompt = DEBATE_PROMPT.format(topic=self.topic, context=self.context, role=agent.entity.role, agent_type=agent.entity.type.value, history=history_str)
                response = self.llm.completion(prompt, system_prompt=f"You are {agent.entity.name}, a {agent.entity.role}.")
                parsed = extract_json(response) or {"position": "neutral", "argument": response[:200], "confidence": 0.5}
                parsed["agent"] = agent.entity.name
                parsed["round"] = round_num
                self.history.append(parsed)
                agent.add_memory(f"Debate ({self.topic}): {parsed.get('argument', '')[:100]}", role="debate")
        return self._synthesize()
    def _synthesize(self) -> Dict[str, Any]:
        arguments_str = "\n".join(f"[{h['agent']}] ({h['position']}, confidence={h.get('confidence', '?')}): {h['argument']}" for h in self.history)
        prompt = SYNTHESIS_PROMPT.format(topic=self.topic, arguments=arguments_str)
        response = self.llm.completion(prompt, system_prompt="You are a neutral moderator synthesizing debate results.")
        result = extract_json(response) or {"decision": "No consensus", "key_points": [], "dissenting_views": [], "confidence": 0.0}
        result["full_history"] = self.history
        return result
