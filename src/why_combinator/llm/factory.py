from typing import Tuple, Optional
import logging
from why_combinator.llm.base import LLMProvider
from why_combinator.llm.ollama import OllamaProvider
from why_combinator.llm.openai import OpenAIProvider
from why_combinator.llm.anthropic import AnthropicProvider
from why_combinator.llm.mock import MockProvider
from why_combinator.llm.huggingface import HuggingfaceProvider
from why_combinator.exceptions import ConfigError
from why_combinator.config import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    HUGGINGFACE_API_KEY,
)

logger = logging.getLogger(__name__)

class LLMFactory:
    """Factory for creating LLM providers."""

    @staticmethod
    def create(provider_spec: str = "ollama:llama3") -> LLMProvider:
        """
        Create an LLM provider from a spec string like 'provider:model'.
        Examples:
            - ollama:llama3
            - openai:gpt-4o
            - anthropic:claude-3-opus-20240229
            
        Implements fallback chain: requested -> ollama -> mock
        """
        try:
            return LLMFactory._create_instance(provider_spec)
        except ConfigError as e:
            logger.warning(f"Failed to initialize provider {provider_spec}: {e}")
            
            # Fallback chain
            # If current attempt was NOT fallback (i.e. checking if we can step down)
            
            # 1. Fallback to Ollama if looking for API-based provider
            if "ollama" not in provider_spec and "mock" not in provider_spec:
                fallback = "ollama:llama3"
                logger.warning(f"Falling back to {fallback}")
                return LLMFactory.create(fallback)
                
            # 2. Fallback to Mock if Ollama fails (or was requested)
            elif "mock" not in provider_spec:
                fallback = "mock"
                logger.warning(f"Falling back to {fallback}")
                return LLMFactory.create(fallback)
                
            # 3. If Mock fails (unlikely) or unknown error, raise
            raise e

    @staticmethod
    def _create_instance(provider_spec: str) -> LLMProvider:
        """Internal creation logic."""
        if ":" in provider_spec:
            provider_type, model = provider_spec.split(":", 1)
        else:
            provider_type, model = provider_spec, None

        provider_type = provider_type.lower()

        if provider_type == "ollama":
            return OllamaProvider(model=model or "llama3")
        elif provider_type == "openai":
            if not OPENAI_API_KEY:
                raise ConfigError("Missing API key for OpenAI. Please set OPENAI_API_KEY environment variable.")
            return OpenAIProvider(model=model or "gpt-4o")
        elif provider_type == "anthropic":
            if not ANTHROPIC_API_KEY:
                raise ConfigError("Missing API key for Anthropic. Please set ANTHROPIC_API_KEY environment variable.")
            return AnthropicProvider(model=model or "claude-3-opus-20240229")
        elif provider_type in ("huggingface", "hf"):
            if not HUGGINGFACE_API_KEY:
                raise ConfigError("Missing API key for Huggingface. Please set HUGGINGFACE_API_KEY environment variable.")
            return HuggingfaceProvider(model=model or "mistralai/Mistral-7B-Instruct-v0.3")
        elif provider_type == "mock":
            return MockProvider()
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
