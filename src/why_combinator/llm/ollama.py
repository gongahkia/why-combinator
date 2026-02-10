import httpx
import logging
import time
from typing import List, Dict, Optional, Any
from why_combinator.llm.base import LLMProvider, RetryPolicy
from why_combinator.config import OLLAMA_BASE_URL

logger = logging.getLogger(__name__)

class OllamaProvider(LLMProvider):
    """Ollama API integration."""
    
    def __init__(self, model: str = "llama3", base_url: str = OLLAMA_BASE_URL, retry_policy: Optional[RetryPolicy] = None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.retry_policy = retry_policy or RetryPolicy()
        self.client = httpx.Client(timeout=60.0)

    def completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": kwargs
        }
        if system_prompt:
            payload["system"] = system_prompt

        for attempt in range(self.retry_policy.max_retries):
            try:
                response = self.client.post(f"{self.base_url}/api/generate", json=payload)
                if response.status_code in self.retry_policy.retryable_status_codes and attempt < self.retry_policy.max_retries - 1:
                    wait = self.retry_policy.backoff_seconds(attempt)
                    logger.warning(f"Ollama returned {response.status_code}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                result = response.json().get("response", "")
                if not result or not result.strip():
                    raise ValueError("Ollama returned an empty response")
                return result
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < self.retry_policy.max_retries - 1:
                    wait = self.retry_policy.backoff_seconds(attempt)
                    logger.warning(f"Ollama completion failed ({e}), retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                logger.error(f"Ollama completion failed after {self.retry_policy.max_retries} attempts: {e}")
                raise
        raise RuntimeError("Ollama completion failed after retries")

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": kwargs
        }
        try:
            response = self.client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Ollama chat completion failed: {e}")
            return ""

    async def async_completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Non-blocking async completion using httpx.AsyncClient."""
        import asyncio
        payload = {"model": self.model, "prompt": prompt, "stream": False, "options": kwargs}
        if system_prompt:
            payload["system"] = system_prompt
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(self.retry_policy.max_retries):
                try:
                    response = await client.post(f"{self.base_url}/api/generate", json=payload)
                    if response.status_code in self.retry_policy.retryable_status_codes and attempt < self.retry_policy.max_retries - 1:
                        await asyncio.sleep(self.retry_policy.backoff_seconds(attempt))
                        continue
                    response.raise_for_status()
                    result = response.json().get("response", "")
                    if not result or not result.strip():
                        raise ValueError("Ollama returned an empty response")
                    return result
                except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
                    if attempt < self.retry_policy.max_retries - 1:
                        await asyncio.sleep(self.retry_policy.backoff_seconds(attempt))
                        continue
                    raise
        raise RuntimeError("Ollama async completion failed after retries")
