from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Iterator
import asyncio


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

    async def async_completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Async completion - default wraps sync in thread."""
        return await asyncio.to_thread(self.completion, prompt, system_prompt, **kwargs)
