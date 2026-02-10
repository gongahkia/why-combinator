import httpx
import logging
import os
from typing import List, Dict, Optional, Any
from why_combinator.llm.base import LLMProvider
from why_combinator.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API integration."""

    def __init__(self, model: str = "gpt-4o", api_key: str = OPENAI_API_KEY):
        self.model = model
        self.api_key = api_key
        self.client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0
        )

    def completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return self.chat_completion(messages, **kwargs)

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            **kwargs
        }
        try:
            response = self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OpenAI chat completion failed: {e}")
            return ""
