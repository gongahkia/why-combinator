from typing import Tuple, Optional
from why_combinator.llm.base import LLMProvider
from why_combinator.llm.ollama import OllamaProvider
from why_combinator.llm.openai import OpenAIProvider
from why_combinator.llm.anthropic import AnthropicProvider
from why_combinator.llm.mock import MockProvider
from why_combinator.llm.huggingface import HuggingfaceProvider

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
        """
        if ":" in provider_spec:
            provider_type, model = provider_spec.split(":", 1)
        else:
            provider_type, model = provider_spec, None

        provider_type = provider_type.lower()

        if provider_type == "ollama":
            return OllamaProvider(model=model or "llama3")
        elif provider_type == "openai":
            return OpenAIProvider(model=model or "gpt-4o")
        elif provider_type == "anthropic":
            return AnthropicProvider(model=model or "claude-3-opus-20240229")
        elif provider_type in ("huggingface", "hf"):
            return HuggingfaceProvider(model=model or "mistralai/Mistral-7B-Instruct-v0.3")
        elif provider_type == "mock":
            return MockProvider()
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
