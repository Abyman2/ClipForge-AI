# Rule: Testing & Verification Standards

## 1. Testing Philosophy

- **Never Claim a Feature Works Without Verification:** Every implemented feature, bugfix, or refactor must be backed by verifiable test execution.
- **Fast Feedback Loop:** Unit tests must be fast, self-contained, and runnable offline without external API access or heavy model downloads.
- **Test Structure:** Place tests in `tests/`:
  - `tests/unit/`: Testing isolated functions, Pydantic validators, word-index boundary snappers, and string formatters.
  - `tests/integration/`: Testing the interaction between FastAPI endpoints, SQLite database operations, and mock media processes.

## 2. Test Execution & Standards

- **Framework:** `pytest` with `pytest-asyncio` for async FastAPI endpoints.
- **HTTP Testing:** Use `httpx.AsyncClient` with `ASGITransport(app=app)` to test API routes in-memory.
- **Mocking External Intelligence:** Tests for `HighlightDiscoveryEngine` must use mocked LLM responses. Never trigger paid or real external LLM API requests during automated CI or unit testing.
- **Media Fixtures:** Use small synthetic fixtures for testing (e.g., a generated 3-second 16kHz WAV file or a 2-second synthetic color-bar MP4 generated via FFmpeg). Never commit multi-megabyte video files into Git.

## 3. Verification Checklist for Changes

Before presenting any task as complete:
1. Run `pytest` on relevant test suites and inspect the output.
2. Verify that modified Python code has valid syntax and imports cleanly.
3. If endpoints were changed, verify response models match frontend TypeScript types.
4. If schemas were updated, verify backward compatibility with existing SQLite project records.
5. Verify that no temporary files or media outputs were left in tracked git directories.

