
import pytest
from unittest.mock import MagicMock, patch, ANY
import httpx
import time
from why_combinator.llm.ollama import OllamaProvider
from why_combinator.llm.openai import OpenAIProvider
from why_combinator.llm.anthropic import AnthropicProvider
from why_combinator.llm.cache import CachedLLMProvider
from why_combinator.llm.base import RetryPolicy
from why_combinator.exceptions import ConfigError
from why_combinator.llm.factory import LLMFactory
import why_combinator.llm.factory as factory_module

class MockResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise httpx.HTTPStatusError(
                f"{self.status_code} Error",
                request=httpx.Request("POST", "http://test"),
                response=self
            )

@patch("httpx.Client")
def test_ollama_retry_on_429(mock_client_cls):
    """Test that OllamaProvider retries on 429 and eventually succeeds."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    
    # Configure mock to fail twice with 429 then succeed
    mock_client.post.side_effect = [
        MockResponse(429), # Fail 1
        MockResponse(429), # Fail 2
        MockResponse(200, {"response": "Success!"}) # Succeed
    ]

    # Use small delay for test speed
    retry_policy = RetryPolicy(initial_delay=0.01, max_retries=3)
    provider = OllamaProvider(retry_policy=retry_policy)

    # Execute
    result = provider.completion("Hello")

    # Verify
    assert result == "Success!"
    assert mock_client.post.call_count == 3

@patch("httpx.Client")
@patch("time.sleep")
def test_openai_exponential_backoff(mock_sleep, mock_client_cls):
    """Test OpenAI provider exponential backoff timing."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    
    # Fail 3 times with 500 error
    mock_client.post.side_effect = [
        MockResponse(500),
        MockResponse(500),
        MockResponse(500),
        MockResponse(200, {"choices": [{"message": {"content": "Success"}}]})
    ]
    
    retry_policy = RetryPolicy(initial_delay=1.0, max_retries=4, backoff_factor=2.0)
    provider = OpenAIProvider(api_key="sk-test", retry_policy=retry_policy)
    
    provider.completion("test")
    
    # Expected delays: 1.0, 2.0, 4.0
    assert mock_sleep.call_count == 3
    mock_sleep.assert_any_call(1.0)
    mock_sleep.assert_any_call(2.0)
    mock_sleep.assert_any_call(4.0)

def test_anthropic_missing_api_key():
    """Test that AnthropicProvider raises ConfigError widely."""
    # We need to ensure global config doesn't have it set, or we simulate it.
    # LLMFactory checks env var before creating.
    # But if we instantiate directly:
    # provider = AnthropicProvider(api_key=None) # This might work if logic is in init?
    # Let's check AnthropicProvider.__init__
    pass # Checked, it doesn't enforce in __init__ currently, LLMFactory enforces it. 
         # But the task says "AnthropicProvider handles missing API key". 
         # I modified LLMFactory to handle it.
         # So I should test LLMFactory creation failure for Anthropic.
    
    # Mock the module-level constant in factory
    with patch("why_combinator.llm.factory.ANTHROPIC_API_KEY", None):
        with pytest.raises(ConfigError, match="Missing API key for Anthropic"):
            LLMFactory.create("anthropic:claude-3")

def test_cached_llm_determinism(tmp_path):
    """Test CachedLLMProvider returns identical response."""
    # Patch CACHE_DIR to use unique temp dir for this test
    with patch("why_combinator.llm.cache.CACHE_DIR", tmp_path):
        mock_provider = MagicMock()
        mock_provider.completion.return_value = "Response 1"
        
        cached = CachedLLMProvider(mock_provider)
        # Ensure dir creation (handled in init usually but CACHE_DIR might be used directly)
        
        # First call - cache miss
        res1 = cached.completion("prompt")
        assert res1 == "Response 1"
        assert mock_provider.completion.call_count == 1
        
        # Change underlying provider return to verify we don't hit it
        mock_provider.completion.return_value = "Response 2"
        
        # Second call - cache hit
        res2 = cached.completion("prompt")
        assert res2 == "Response 1" 
        # Call count should STILL be 1 (metrics/logs might show hit)
        assert mock_provider.completion.call_count == 1


def test_llm_factory_fallback():
    """Test fallback chain: OpenAI (fails) -> Ollama (success)."""
    # Mock ConfigError when creating OpenAI
    with patch("why_combinator.llm.factory.OpenAIProvider", side_effect=ConfigError("No Key")):
        # Mock successful Ollama creation
        with patch("why_combinator.llm.factory.OllamaProvider") as mock_ollama:
             mock_instance = MagicMock()
             mock_ollama.return_value = mock_instance
             
             # Call create with OpenAI spec
             provider = LLMFactory.create("openai:gpt-4")
             
             # Should return the Ollama instance
             assert provider == mock_instance
             # Should have logged warning (can't easily check without log capture, but behavior confirms)

def test_llm_factory_fallback_to_mock():
    """Test fallback chain: OpenAI (fails) -> Ollama (fails) -> Mock (success)."""
    with patch("why_combinator.llm.factory.OpenAIProvider", side_effect=ConfigError("No Key")):
        with patch("why_combinator.llm.factory.OllamaProvider", side_effect=ConfigError("No Ollama")):
            with patch("why_combinator.llm.factory.MockProvider") as mock_mock:
                mock_instance = MagicMock()
                mock_mock.return_value = mock_instance
                
                provider = LLMFactory.create("openai:gpt-4")
                
                assert provider == mock_instance

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main(["-v", __file__]))

