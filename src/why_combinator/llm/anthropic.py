import httpx
import logging
import os
from typing import List, Dict, Optional, Any
from why_combinator.llm.base import LLMProvider
from why_combinator.config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic API integration."""

    def __init__(self, model: str = "claude-3-opus-20240229", api_key: str = ANTHROPIC_API_KEY):
        self.model = model
        self.api_key = api_key
        self.client = httpx.Client(
            base_url="https://api.anthropic.com/v1",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            timeout=60.0
        )

    def completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        # Anthropic uses messages API exclusively now for newer models
        messages = [{"role": "user", "content": prompt}]
        return self.chat_completion(messages, system=system_prompt, **kwargs)

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # Extract system prompt if present in kwargs to move to top level
        system = kwargs.pop('system', None)
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.pop('max_tokens', 1024),
            **kwargs
        }
        if system:
            payload["system"] = system

        try:
            response = self.client.post("/messages", json=payload)
            response.raise_for_status()
            return response.json()["content"][0]["text"]
        except Exception as e:
            logger.error(f"Anthropic chat completion failed: {e}")
            return ""
