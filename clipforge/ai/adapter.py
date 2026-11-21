"""Provider-Independent LLM Adapter Interface.

Decouples ClipForge AI from specific AI providers. Supports both
OpenAI-compatible and Anthropic protocol payloads with secret scrubbing,
token usage tracking, and markdown JSON extraction.
"""

import json
import re
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, SecretStr
from clipforge.core.config import settings
from clipforge.core.logging import sanitize_headers, logger


class HighlightCandidate(BaseModel):
    """Pydantic schema for an extracted highlight moment."""
    start_word_index: int
    end_word_index: int
    title: str
    hook: str
    description: str = ""
    rationale: str = ""
    category: str = "insight"
    engagement_score: float = 7.0


class HighlightDiscoveryResponse(BaseModel):
    """Schema for the LLM structured JSON response."""
    highlights: List[HighlightCandidate] = []


HIGHLIGHT_SYSTEM_PROMPT = """You are an expert short-form video producer and viral clip editor.
Your task is to analyze an indexed transcript of a video and identify the most engaging, self-contained highlight moments suitable for 9:16 vertical shorts (TikTok, YouTube Shorts, Instagram Reels).

CRITICAL INSTRUCTIONS:
1. Every word in the transcript is formatted with its integer word index in brackets: [index] word.
2. You must define each clip boundary STRICTLY by `start_word_index` and `end_word_index`.
3. NEVER calculate or output timestamps (seconds). Use ONLY the integer word indices.
4. Each clip must be a coherent, self-contained thought or story that makes complete sense on its own.
5. Target duration is between 15 and 90 seconds (typically 35 to 220 words spoken at normal conversational pace).
6. Ensure the start of the clip has an immediate hook that grabs the viewer's attention.
7. Ensure the end of the clip concludes cleanly on terminal sentence punctuation (. ? !).
8. Categories can be: "insight", "story", "opinion", "tutorial", "humor", "hot-take".

You must output valid JSON conforming exactly to this structure:
{
  "highlights": [
    {
      "start_word_index": 15,
      "end_word_index": 82,
      "title": "Short Punchy Title",
      "hook": "The opening sentence or attention grabber",
      "description": "One sentence summary of the clip content",
      "rationale": "Why this specific moment will retain viewers and drive shares",
      "category": "insight",
      "engagement_score": 8.5
    }
  ]
}
"""


def build_highlight_user_prompt(transcript_chunk_text: str) -> str:
    """Format the user prompt containing indexed transcript text."""
    return (
        "Here is the indexed video transcript segment:\n\n"
        f"{transcript_chunk_text}\n\n"
        "Identify 1 to 4 of the most compelling, high-retention highlight moments. "
        "Return your answer as a valid JSON object with the 'highlights' array."
    )


def clean_json_markdown(raw_response: str) -> str:
    """Strip markdown code fence blocks from LLM JSON response."""
    cleaned = raw_response.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        cleaned = match.group(1).strip()
    return cleaned


class LLMAdapterInterface:
    """Universal interface for external LLM intelligence."""

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[SecretStr] = None,
        model: Optional[str] = None,
        protocol: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        self.api_base = api_base or settings.llm_api_base
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.protocol = protocol or settings.llm_protocol
        self.timeout = timeout
        self.max_retries = max_retries

    @property
    def has_api_key(self) -> bool:
        """Check whether an active API key is configured."""
        if not self.api_key:
            return False
        return bool(self.api_key.get_secret_value().strip())

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

    def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Execute HTTP request to configured LLM provider with retries and exponential backoff."""
        if not self.has_api_key:
            raise ValueError("No LLM API key configured.")

        payload = self.format_request_payload(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Build endpoint URL based on protocol
        base = self.api_base.rstrip("/")
        if self.protocol == "anthropic":
            url = f"{base}/messages" if not base.endswith("/messages") else base
        else:
            url = f"{base}/chat/completions" if not base.endswith("/chat/completions") else base

        headers = self.get_auth_headers()
        body_bytes = json.dumps(payload).encode("utf-8")

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"[LLMAdapter] Sending request to {url} (model={self.model}, protocol={self.protocol}, attempt={attempt})"
                )
                req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    return self._extract_response_content(resp_data)
            except urllib.error.HTTPError as e:
                status_code = e.code
                error_body = e.read().decode("utf-8", errors="ignore")
                logger.warning(
                    f"[LLMAdapter] HTTP {status_code} on attempt {attempt}: {error_body[:200]}"
                )
                # Retry on rate-limiting or server errors
                if status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    backoff = (2 ** attempt) * 1.5
                    time.sleep(backoff)
                    continue
                raise RuntimeError(f"LLM API error (HTTP {status_code}): {error_body}") from e
            except Exception as e:
                logger.error(f"[LLMAdapter] Network/Request error on attempt {attempt}: {e}")
                if attempt < self.max_retries:
                    time.sleep(2.0 * attempt)
                    continue
                raise

        raise RuntimeError("LLM request failed after maximum retries.")

    def _extract_response_content(self, raw_resp: Dict[str, Any]) -> Dict[str, Any]:
        """Extract text content and parse structured JSON from provider response."""
        content_text = ""
        if self.protocol == "anthropic":
            contents = raw_resp.get("content", [])
            for block in contents:
                if block.get("type") == "text":
                    content_text += block.get("text", "")
        else:
            choices = raw_resp.get("choices", [])
            if choices:
                content_text = choices[0].get("message", {}).get("content", "")

        cleaned_json = clean_json_markdown(content_text)
        try:
            parsed = json.loads(cleaned_json)
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"[LLMAdapter] Failed to parse JSON from LLM: {cleaned_json[:300]}")
            raise ValueError(f"LLM response was not valid JSON: {e}") from e
