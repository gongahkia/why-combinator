import httpx
import logging
import os
import asyncio
import time
from typing import List, Dict, Optional, Any
from why_combinator.llm.base import LLMProvider
from why_combinator.config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 503}


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

        for attempt in range(3):
            try:
                response = self.client.post("/messages", json=payload)
                if response.status_code in RETRYABLE_STATUS_CODES and attempt < 2:
                    wait = 2 ** attempt
                    logger.warning(f"Anthropic returned {response.status_code}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                return response.json()["content"][0]["text"]
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < 2:
                    wait = 2 ** attempt
                    logger.warning(f"Anthropic completion failed ({e}), retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                logger.error(f"Anthropic completion failed after 3 attempts: {e}")
                return ""
        return ""

    async def async_completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        messages = [{"role": "user", "content": prompt}]
        system = system_prompt
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.pop('max_tokens', 1024),
            **kwargs
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(
            base_url="https://api.anthropic.com/v1",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            timeout=60.0
        ) as client:
            for attempt in range(3):
                try:
                    response = await client.post("/messages", json=payload)
                    if response.status_code in RETRYABLE_STATUS_CODES and attempt < 2:
                        wait = 2 ** attempt
                        logger.warning(f"Anthropic returned {response.status_code}, retrying in {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    response.raise_for_status()
                    return response.json()["content"][0]["text"]
                except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
                    if attempt < 2:
                        wait = 2 ** attempt
                        logger.warning(f"Anthropic async completion failed ({e}), retrying in {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    logger.error(f"Anthropic async completion failed after 3 attempts: {e}")
                    return ""
        return ""
