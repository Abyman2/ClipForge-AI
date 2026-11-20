"""Provider-Independent LLM Adapter Interface.

Decouples ClipForge AI from specific AI providers. Supports both
OpenAI-compatible and Anthropic protocol payloads with secret scrubbing.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, SecretStr
from clipforge.core.config import settings
from clipforge.core.logging import sanitize_headers, logger


class HighlightCandidate(BaseModel):
    """Pydantic schema for an extracted highlight moment."""
    start_word_index: int
    end_word_index: int
    title: str
    hook: str
    rationale: str
    engagement_score: float = 0.0


class LLMAdapterInterface:
    """Universal interface for external LLM intelligence."""

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[SecretStr] = None,
        model: Optional[str] = None,
        protocol: Optional[str] = None,
    ):
        self.api_base = api_base or settings.llm_api_base
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.protocol = protocol or settings.llm_protocol

    def get_auth_headers(self) -> Dict[str, str]:
        """Construct authentication headers based on configured protocol."""
        key_val = self.api_key.get_secret_value() if self.api_key else ""
        if self.protocol == "anthropic":
            return {
                "x-api-key": key_val,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        return {
            "Authorization": f"Bearer {key_val}",
            "Content-Type": "application/json",
        }

    def get_sanitized_headers(self) -> Dict[str, Any]:
        """Return headers with secrets scrubbed for safe logging."""
        return sanitize_headers(self.get_auth_headers())

    def format_request_payload(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Format request payload according to protocol."""
        if self.protocol == "anthropic":
            return {
                "model": self.model,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

        # Default: OpenAI-compatible
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

