from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Iterator, Set
import asyncio


@dataclass(frozen=True)
class RetryPolicy:
    """Retry policy for transient LLM API failures."""
    max_retries: int = 3
    backoff_base: float = 2.0
    retryable_status_codes: Set[int] = field(default_factory=lambda: {429, 500, 503})

    def backoff_seconds(self, attempt: int) -> float:
        return self.backoff_base ** attempt


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
