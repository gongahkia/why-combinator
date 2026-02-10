import httpx
import logging
import os
import asyncio
from typing import List, Dict, Optional, Any
from why_combinator.llm.base import LLMProvider
from why_combinator.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 503}


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
        for attempt in range(3):
            try:
                response = self.client.post("/chat/completions", json=payload)
                if response.status_code in RETRYABLE_STATUS_CODES and attempt < 2:
                    wait = 2 ** attempt
                    logger.warning(f"OpenAI returned {response.status_code}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < 2:
                    wait = 2 ** attempt
                    logger.warning(f"OpenAI completion failed ({e}), retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                logger.error(f"OpenAI completion failed after 3 attempts: {e}")
                return ""
        return ""

    async def async_completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            **kwargs
        }
        async with httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0
        ) as client:
            for attempt in range(3):
                try:
                    response = await client.post("/chat/completions", json=payload)
                    if response.status_code in RETRYABLE_STATUS_CODES and attempt < 2:
                        wait = 2 ** attempt
                        logger.warning(f"OpenAI returned {response.status_code}, retrying in {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    response.raise_for_status()
                    return response.json()["choices"][0]["message"]["content"]
                except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
                    if attempt < 2:
                        wait = 2 ** attempt
                        logger.warning(f"OpenAI async completion failed ({e}), retrying in {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    logger.error(f"OpenAI async completion failed after 3 attempts: {e}")
                    return ""
        return ""
