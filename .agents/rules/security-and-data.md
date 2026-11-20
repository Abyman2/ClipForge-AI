# Rule: Security, API Credentials & User Data

## 1. Secret Protection & API Key Management

- **Zero Hardcoded Secrets:** API keys, gateway tokens, passwords, or personal credentials must NEVER be hardcoded into any Python file, React component, configuration JSON, or test script.
- **Environment Loading:** Read credentials strictly through environment variables or `.env` files via Pydantic `BaseSettings`.
- **Secret Redaction:**
  - All logging formatters and HTTP clients must intercept request headers and scrub values for `Authorization`, `x-api-key`, `api-key`, and `token`.
  - API responses sent to the frontend must NEVER echo the raw API key. Use masked representations (e.g., `sk-ant...1a2b`).
- **Git Commit Gate:** Never commit `.env` or files containing secret signatures. Verify `.gitignore` rules before every commit.

## 2. User Data Privacy & Local Isolation

- **Local Media Privacy:** User videos, audio recordings, facial landmark coordinates, and derived media assets must NEVER be transmitted to external servers, telemetry collectors, or cloud storage.
- **External AI Boundary:** The external LLM API gateway must receive **only plain text transcripts** and structural prompts. No video frames, audio samples, or personally identifiable metadata may be transmitted.
- **Path Sanitization:** User-supplied file paths or project names must be strictly validated and sanitized to prevent directory traversal attacks (`../`). File access must be scoped to the workspace and designated data directories.

## 3. Dependency Safety

- Inspect any new Python or Node.js package before installing.
- Never execute untrusted third-party installation scripts (`curl | bash` or arbitrary `.bat`/`.ps1` installers) without prior line-by-line inspection.
- Maintain pinned version numbers in `requirements.txt` and `package.json` to prevent supply-chain drift.

