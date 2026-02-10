import httpx
import logging
from typing import List, Dict, Optional, Any
from sim_city.llm.base import LLMProvider
from sim_city.config import OLLAMA_BASE_URL

logger = logging.getLogger(__name__)

class OllamaProvider(LLMProvider):
    """Ollama API integration."""
    
    def __init__(self, model: str = "llama3", base_url: str = OLLAMA_BASE_URL):
        self.model = model
        self.base_url = base_url.rstrip("/")
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
            
        try:
            response = self.client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama completion failed: {e}")
            return ""

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
