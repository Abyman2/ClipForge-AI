---
name: python-fastapi
description: >-
  Use this skill when developing, refactoring, or reviewing Python backend code, FastAPI
  routes, Pydantic schemas, database operations, or background workers in ClipForge AI.
---

# Python & FastAPI Development Skill

This skill defines the technical standards, patterns, and procedures for building the ClipForge AI backend using Python 3.11+, FastAPI, Pydantic v2, and SQLite.

## When to Use This Skill
- Creating or updating REST API endpoints in `clipforge/api/`.
- Defining Pydantic v2 schemas for requests, responses, and LLM payloads.
- Implementing SQLite database models and queries.
- Writing asynchronous pipeline workers and Server-Sent Events (SSE) brokers.

## Step-by-Step Implementation Procedure

1. **Define Domain Schemas First:**
   - Create typed Pydantic models in `clipforge/api/schemas/` or `clipforge/core/models/`.
   - Ensure all fields have type annotations and sensible defaults.
   - Use `SecretStr` for any sensitive API credentials.

2. **Implement Business Logic in Service Modules:**
   - Place media processing or pipeline orchestration logic in `clipforge/media/` or `clipforge/pipeline/`.
   - Keep business logic completely decoupled from FastAPI's `Request` or `Response` objects.

3. **Expose Endpoints via Modular APIRouters:**
   - Define routes in dedicated modules (`clipforge/api/routes/projects.py`, `clips.py`, etc.).
   - Declare explicit `response_model` and HTTP status codes on every route.
   - Use `Depends` for shared dependencies (DB sessions, settings).

4. **Handle Long-Running Operations Safely:**
   - Never run blocking synchronous operations (FFmpeg calls, Whisper inference) directly in the async event loop.
   - Wrap synchronous calls with `asyncio.to_thread(sync_func, *args)`.
   - Update job progress in the SQLite database and broadcast status via SSE.

5. **Validate with Automated Tests:**
   - Write unit tests in `tests/unit/` using `pytest`.
   - Test API endpoints using `httpx.AsyncClient` with `ASGITransport`.

## Technical Standards & Patterns
- **Database Concurrency:** Always configure SQLite with `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;`.
- **Secret Redaction:** Custom logging interceptors must scrub `Authorization` and `x-api-key` headers from all logs.
- **Type Safety:** Maintain 100% type annotation coverage on all new functions.

## Common Mistakes to Avoid
- **Event Loop Blocking:** Calling `subprocess.run()` or `whisper.transcribe()` directly inside an `async def` route without `asyncio.to_thread`.
- **Missing Response Models:** Leaving route return types unvalidated.
- **Exposing Secrets:** Returning raw API keys in settings endpoints or error stack traces.

## Verification Checklist
- [ ] All functions have strict type annotations.
- [ ] Pydantic v2 syntax used (`@field_validator`, `model_dump()`).
- [ ] No blocking I/O inside the async event loop.
- [ ] SQLite session management cleanly closes connections.
- [ ] Automated tests pass with `pytest`.

