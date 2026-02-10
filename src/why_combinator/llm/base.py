from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Iterator


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate a completion for the given prompt."""
        pass
    
    @abstractmethod
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate a chat completion for the given messages."""
        pass
