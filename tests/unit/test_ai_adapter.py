"""Unit tests for provider-agnostic LLM adapter interface."""

from pydantic import SecretStr
from clipforge.ai.adapter import LLMAdapterInterface


def test_openai_compatible_payload():
    """Verify payload structure for OpenAI-compatible gateway."""
    adapter = LLMAdapterInterface(
        api_base="https://custom.gateway.internal/v1",
        api_key=SecretStr("test-secret-key"),
        model="qwen-2.5-72b",
        protocol="openai_compatible",
    )
    headers = adapter.get_auth_headers()
    assert headers["Authorization"] == "Bearer test-secret-key"

    sanitized = adapter.get_sanitized_headers()
    assert sanitized["Authorization"] == "***REDACTED***"

    payload = adapter.format_request_payload("System prompt", "User prompt")
    assert payload["model"] == "qwen-2.5-72b"
    assert len(payload["messages"]) == 2
    assert payload["response_format"] == {"type": "json_object"}


def test_anthropic_payload():
    """Verify payload structure for Anthropic protocol."""
    adapter = LLMAdapterInterface(
        api_base="https://api.anthropic.com/v1",
        api_key=SecretStr("sk-ant-test-12345"),
        model="claude-3-5-sonnet",
        protocol="anthropic",
    )
    headers = adapter.get_auth_headers()
    assert headers["x-api-key"] == "sk-ant-test-12345"
    assert "anthropic-version" in headers

    sanitized = adapter.get_sanitized_headers()
    assert sanitized["x-api-key"] == "***REDACTED***"

    payload = adapter.format_request_payload("System prompt", "User prompt")
    assert payload["system"] == "System prompt"
    assert payload["model"] == "claude-3-5-sonnet"

