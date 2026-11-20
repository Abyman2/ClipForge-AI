# Rule: Python & FastAPI Coding Standards

## 1. Language & Version Requirements

- **Python Version:** Python 3.11 or 3.12 (64-bit).
- **Type Annotations:** All function signatures, method parameters, and return types must be fully type-annotated (`typing` / built-in generics). Avoid untyped `Any` wherever possible.
- **Style Guide:** Adhere strictly to PEP 8. Use standard naming: `snake_case` for functions/variables, `PascalCase` for classes, `SCREAMING_SNAKE_CASE` for constants.

## 2. FastAPI Standards

- **Asynchronous Handlers:** Endpoint functions performing I/O (database queries, network requests, SSE broadcasting) must be defined as `async def`.
- **CPU/Subprocess Offloading:** Long-running CPU-bound tasks (FFmpeg calls, transcription, face tracking) must NOT be executed directly inside the async event loop. Offload them to `asyncio.to_thread` or a background thread executor.
- **Dependency Injection:** Use FastAPI's `Depends` for database sessions, configuration instances, and shared services.
- **Router Modularization:** Endpoints must be grouped into dedicated `APIRouter` modules under `clipforge/api/routes/` (e.g., `projects.py`, `clips.py`, `settings.py`).
- **Response Models:** Always declare explicit `response_model` schemas on routes to guarantee consistent serialization and automatic documentation.

## 3. Pydantic v2 Usage

- Use Pydantic v2 for all request bodies, response models, configuration settings, and LLM JSON parsing.
- Use `pydantic_settings.BaseSettings` for environment variable loading.
- Sensitive fields (API keys) must use `pydantic.SecretStr` to prevent accidental serialization in `repr()`, logs, or API responses.
- Use `@field_validator` and `@model_validator` for domain logic verification (e.g., verifying `start_word_index < end_word_index`).

## 4. Error Handling & Logging

- **Explicit Exceptions:** Raise typed HTTP exceptions (`fastapi.HTTPException`) with clear, user-actionable `detail` messages.
- **Log Formatting:** Use Python's standard `logging` module. Never use `print()` for diagnostic output.
- **No Unhandled Panics:** Wrap external process executions and API requests in explicit `try...except` blocks that capture failure details into the `Job` database record.

