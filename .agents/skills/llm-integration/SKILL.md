---
name: llm-integration
description: >-
  Use this skill when implementing, configuring, or testing the external LLM integration,
  protocol adapters (Anthropic / OpenAI), highlight discovery prompts, or word-index validation.
---

# LLM Integration & Highlight Discovery Skill

This skill governs the integration with external LLM APIs, handling protocol adaptability, prompt construction, highlight discovery, and deterministic boundary validation.

## When to Use This Skill
- Implementing or updating `UniversalLLMClient` in `clipforge/ai/`.
- Configuring API protocols (`openai_compatible` vs. `anthropic`) and custom base URLs.
- Designing or tuning highlight discovery prompts.
- Implementing the 4-rule word-index validation pipeline.
- Tracking token usage and sanitizing API logs.

## Step-by-Step Procedure

1. **Configure Universal HTTP Client:**
   - Instantiate `httpx.AsyncClient` with configurable timeout (default 60s) and retry handlers.
   - Support protocol switching:
     - `openai_compatible`: Transmit to `{base_url}/chat/completions` with `Authorization: Bearer {key}`.
     - `anthropic`: Transmit to `{base_url}/messages` with `x-api-key: {key}` and `anthropic-version: 2023-06-01`.

2. **Sanitize Headers & Payloads:**
   - Ensure all request logging passes through an in-memory scrubber masking `Authorization` and `x-api-key`.
   - Never print raw keys to console, logs, or frontend responses.

3. **Construct Highlight Discovery Prompt:**
   - Provide indexed words `[index] word` or numbered segments.
   - Enforce structured JSON output requesting:
     - `start_word_index` (int)
     - `end_word_index` (int)
     - `title` (string)
     - `hook` (string)
     - `rationale` (string)
     - `engagement_score` (float 0-10)

4. **Execute Request with Exponential Backoff:**
   - Handle HTTP 429 (Rate Limit) and 503 (Overload) with randomized jitter retries (up to 3 attempts).
   - Track prompt and completion tokens, logging usage to SQLite.

5. **Apply Deterministic 4-Rule Validation Pipeline:**
   - Pass candidate objects into `WordIndexValidator`:
     - **Rule 1 (Bounds):** $0 \le \text{start} < \text{end} < N$. Discard if invalid.
     - **Rule 2 (Sentence Completeness):** Snap backward to sentence start (capital letter / pause $>0.75\text{s}$) and forward to terminal punctuation (`.`, `?`, `!`).
     - **Rule 3 (Duration):** Derive $\Delta T = \text{words}[\text{end}].\text{end} - \text{words}[\text{start}].\text{start}$. Enforce $15.0\text{s} \le \Delta T \le 90.0\text{s}$.
     - **Rule 4 (Dead-Air):** Verify no internal silent gap exceeds 3.0 seconds.

6. **Derive Verified Physical Timestamps:**
   - Set `clip.start_time = transcript.words[start_word_index].start`.
   - Set `clip.end_time = transcript.words[end_word_index].end`.

## Technical Standards
- **Zero Hallucinated Timestamps:** The LLM must NEVER output raw seconds or time strings. Only integer word indices are accepted.
- **Provider Independence:** Do not hardcode Anthropic or OpenAI SDKs. Use raw `httpx` to guarantee compatibility with custom gateways, OpenRouter, or local vLLM.

## Common Mistakes to Avoid
- **Allowing LLM to Calculate Time:** Asking the LLM "give me timestamps" always results in hallucinated or rounded cuts. Always use word indices.
- **Missing Token Accounting:** Failing to extract `usage` tokens leads to surprise API bills on long videos.
- **Strict JSON Parsing Panics:** Crashing when the LLM wraps JSON in ````json markdown. Always use a regex cleaner before parsing.

## Verification Checklist
- [ ] Universal client supports both Anthropic and OpenAI protocols.
- [ ] Logging masks all secret keys.
- [ ] LLM output parses into Pydantic schema with automatic markdown stripping.
- [ ] All 4 validation rules execute before storing candidate clips.
- [ ] Physical start/end timestamps match Whisper's verified word timings.

