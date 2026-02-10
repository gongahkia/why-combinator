"""Multi-turn conversation system between agents."""
import logging
from typing import List, Dict, Any, Optional
from sim_city.agent.base import BaseAgent
from sim_city.llm.base import LLMProvider
from sim_city.utils.parsing import extract_json

logger = logging.getLogger(__name__)

CONVERSATION_PROMPT = """You are {name} ({role}, {agent_type}) in a multi-turn conversation.
Topic: {topic}
Conversation so far:
{history}
Respond naturally in character. Output JSON:
{{"message": "your response", "wants_to_continue": true/false, "action": "optional action to take based on conversation"}}"""

class Conversation:
    """Multi-turn conversation between two or more agents."""
    def __init__(self, topic: str, llm_provider: LLMProvider, max_turns: int = 6):
        self.topic = topic
        self.llm = llm_provider
        self.max_turns = max_turns
        self.transcript: List[Dict[str, str]] = []
    def run(self, participants: List[BaseAgent]) -> List[Dict[str, str]]:
        """Run conversation, agents take turns responding."""
        for turn in range(self.max_turns):
            speaker = participants[turn % len(participants)]
            history_str = "\n".join(f"{t['speaker']}: {t['message']}" for t in self.transcript) or "Conversation just started."
            prompt = CONVERSATION_PROMPT.format(
                name=speaker.entity.name, role=speaker.entity.role,
                agent_type=speaker.entity.type.value, topic=self.topic, history=history_str
            )
            response = self.llm.completion(prompt, system_prompt=f"You are {speaker.entity.name} in a business conversation.")
            parsed = extract_json(response) or {"message": response[:200], "wants_to_continue": True}
            entry = {"speaker": speaker.entity.name, "speaker_id": speaker.entity.id, "message": parsed.get("message", ""), "turn": turn}
            self.transcript.append(entry)
            speaker.add_memory(f"Conversation ({self.topic}): said '{parsed.get('message', '')[:80]}'", role="conversation")
            if not parsed.get("wants_to_continue", True):
                break
        return self.transcript

class ConversationManager:
    """Manages and triggers conversations between agents."""
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider
        self.history: List[Dict[str, Any]] = []
    def trigger_conversation(self, agents: List[BaseAgent], topic: str, max_turns: int = 6) -> List[Dict[str, str]]:
        conv = Conversation(topic, self.llm, max_turns)
        transcript = conv.run(agents)
        self.history.append({"topic": topic, "participants": [a.entity.name for a in agents], "transcript": transcript})
        return transcript
