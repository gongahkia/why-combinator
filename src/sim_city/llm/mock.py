from typing import List, Dict, Any, Optional
import json
import random
from sim_city.llm.base import LLMProvider

class MockProvider(LLMProvider):
    """Mock LLM provider for testing."""
    
    def completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        # Generate a fake JSON response
        actions = ["buy", "sell", "post_review", "invest", "complain", "partner"]
        action = random.choice(actions)
        
        response = {
            "thought_process": "This is a mock thought process.",
            "action_type": action,
            "action_details": {
                "target": "startup",
                "content": f"Mock action {action} executed."
            }
        }
        return json.dumps(response)

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        return self.completion(messages[-1]["content"])
