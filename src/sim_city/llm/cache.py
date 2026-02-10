import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from sim_city.llm.base import LLMProvider
from sim_city.config import DATA_DIR

logger = logging.getLogger(__name__)
CACHE_DIR = DATA_DIR / "llm_cache"

class CachedLLMProvider(LLMProvider):
    """Wraps any LLMProvider with a disk-based response cache."""
    def __init__(self, provider: LLMProvider):
        self.provider = provider
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    def _cache_key(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        h = hashlib.sha256(f"{system_prompt or ''}||{prompt}".encode()).hexdigest()
        return h
    def _get_cached(self, key: str) -> Optional[str]:
        path = CACHE_DIR / f"{key}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return data.get("response")
            except Exception:
                pass
        return None
    def _set_cached(self, key: str, response: str):
        path = CACHE_DIR / f"{key}.json"
        try:
            path.write_text(json.dumps({"response": response}))
        except Exception as e:
            logger.warning(f"Failed to write cache: {e}")
    def completion(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        key = self._cache_key(prompt, system_prompt)
        cached = self._get_cached(key)
        if cached is not None:
            logger.debug(f"Cache hit: {key[:12]}")
            return cached
        response = self.provider.completion(prompt, system_prompt, **kwargs)
        if response:
            self._set_cached(key, response)
        return response
    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        key = self._cache_key(json.dumps(messages, sort_keys=True))
        cached = self._get_cached(key)
        if cached is not None:
            logger.debug(f"Cache hit: {key[:12]}")
            return cached
        response = self.provider.chat_completion(messages, **kwargs)
        if response:
            self._set_cached(key, response)
        return response
