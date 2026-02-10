import logging
import asyncio
import time
from typing import List, Dict, Optional, Any
from why_combinator.llm.base import LLMProvider, RetryPolicy
from why_combinator.config import HUGGINGFACE_API_KEY

logger = logging.getLogger(__name__)

class HuggingfaceProvider(LLMProvider):
    """Huggingface Inference API integration (remote). Falls back to local transformers if available."""
    def __init__(self, model: str = "mistralai/Mistral-7B-Instruct-v0.3", api_key: str = HUGGINGFACE_API_KEY, retry_policy: Optional[RetryPolicy] = None):
        self.model = model
        self.api_key = api_key
        self.retry_policy = retry_policy or RetryPolicy()
        self._local_pipeline = None
        if not self.api_key:
            self._try_load_local()
    def _try_load_local(self):
        """Try loading model locally via transformers pipeline."""
        try:
            from transformers import pipeline
            logger.info(f"Loading local HF model: {self.model}")
            self._local_pipeline = pipeline("text-generation", model=self.model, max_new_tokens=512)
            logger.info(f"Local HF model loaded: {self.model}")
        except ImportError:
            logger.warning("transformers not installed. Install with: pip install transformers torch")
        except Exception as e:
            logger.warning(f"Failed to load local HF model {self.model}: {e}")
    def completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        if self._local_pipeline: # local inference
            try:
                result = self._local_pipeline(full_prompt, max_new_tokens=kwargs.get("max_tokens", 512), do_sample=True, temperature=kwargs.get("temperature", 0.7))
                return result[0]["generated_text"][len(full_prompt):].strip()
            except Exception as e:
                logger.error(f"Local HF inference failed: {e}")
                return ""
        if self.api_key: # remote API
            try:
                import httpx
                for attempt in range(self.retry_policy.max_retries):
                    try:
                        response = httpx.post(
                            f"https://api-inference.huggingface.co/models/{self.model}",
                            headers={"Authorization": f"Bearer {self.api_key}"},
                            json={"inputs": full_prompt, "parameters": {"max_new_tokens": kwargs.get("max_tokens", 512), "temperature": kwargs.get("temperature", 0.7)}},
                            timeout=120.0
                        )
                        if response.status_code in self.retry_policy.retryable_status_codes and attempt < self.retry_policy.max_retries - 1:
                            wait = self.retry_policy.backoff_seconds(attempt)
                            logger.warning(f"HF API returned {response.status_code}, retrying in {wait}s...")
                            time.sleep(wait)
                            continue
                        response.raise_for_status()
                        data = response.json()
                        if isinstance(data, list) and data:
                            return data[0].get("generated_text", "")[len(full_prompt):].strip()
                        return ""
                    except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
                        if attempt < self.retry_policy.max_retries - 1:
                            wait = self.retry_policy.backoff_seconds(attempt)
                            logger.warning(f"HF API inference failed ({e}), retrying in {wait}s...")
                            time.sleep(wait)
                            continue
                        logger.error(f"HF API inference failed after {self.retry_policy.max_retries} attempts: {e}")
                        return ""
            except Exception as e:
                logger.error(f"HF API inference failed: {e}")
                return ""
        logger.error("No HF API key and local transformers unavailable.")
        return ""
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_msgs = [m["content"] for m in messages if m["role"] == "user"]
        prompt = "\n".join(user_msgs)
        return self.completion(prompt, system_prompt=system, **kwargs)

    async def async_completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        if self._local_pipeline:
            # Run local pipeline in thread pool
            return await asyncio.to_thread(self.completion, prompt, system_prompt, **kwargs)
        if self.api_key:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=120.0) as client:
                    for attempt in range(self.retry_policy.max_retries):
                        try:
                            response = await client.post(
                                f"https://api-inference.huggingface.co/models/{self.model}",
                                headers={"Authorization": f"Bearer {self.api_key}"},
                                json={"inputs": full_prompt, "parameters": {"max_new_tokens": kwargs.get("max_tokens", 512), "temperature": kwargs.get("temperature", 0.7)}}
                            )
                            if response.status_code in self.retry_policy.retryable_status_codes and attempt < self.retry_policy.max_retries - 1:
                                wait = self.retry_policy.backoff_seconds(attempt)
                                logger.warning(f"HF API returned {response.status_code}, retrying in {wait}s...")
                                await asyncio.sleep(wait)
                                continue
                            response.raise_for_status()
                            data = response.json()
                            if isinstance(data, list) and data:
                                return data[0].get("generated_text", "")[len(full_prompt):].strip()
                            return ""
                        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
                            if attempt < self.retry_policy.max_retries - 1:
                                wait = self.retry_policy.backoff_seconds(attempt)
                                logger.warning(f"HF API async inference failed ({e}), retrying in {wait}s...")
                                await asyncio.sleep(wait)
                                continue
                            logger.error(f"HF API async inference failed after {self.retry_policy.max_retries} attempts: {e}")
                            return ""
            except Exception as e:
                logger.error(f"HF API async inference failed: {e}")
                return ""
        logger.error("No HF API key and local transformers unavailable.")
        return ""
