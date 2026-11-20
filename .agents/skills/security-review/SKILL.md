---
name: security-review
description: >-
  Use this skill when auditing code for secret leakage, checking third-party dependencies,
  verifying license compliance, or reviewing user data privacy in ClipForge AI.
---

# Security & License Review Skill

This skill governs security auditing, credential protection, dependency vetting, and open-source license compliance for ClipForge AI.

## When to Use This Skill
- Before staging or committing new code.
- When adding any new Python package or NPM dependency.
- When reviewing API credential storage or logging mechanisms.
- When checking third-party code licenses for commercial compatibility.

## Step-by-Step Review Procedure

1. **Scan for Hardcoded Secrets:**
   - Search the codebase for accidental API keys or token patterns (`sk-ant-`, `sk-`, `ghp_`, `Bearer `).
   - Verify that credentials are read exclusively from environment variables via Pydantic `SecretStr`.

2. **Verify Logging Sanitization:**
   - Check all HTTP client logging interceptors.
   - Verify that `Authorization`, `x-api-key`, and `api-key` headers are replaced with `***REDACTED***`.
   - Verify that error handlers and API responses never echo raw secret values.

3. **Audit Third-Party Dependencies:**
   - Before adding any package to `requirements.txt` or `package.json`, inspect its upstream license.
   - Ensure the license is commercially permissible (MIT, Apache 2.0, BSD 3-Clause, Public Domain).
   - **Blacklist Enforcement:**
     - `paundrapf/PaunClip`: No license (All Rights Reserved). Zero code reuse.
     - `mutonby/openshorts` (`cloud/` directory): Proprietary commercial license. Strictly blacklisted.

4. **Verify Media Privacy & Network Boundaries:**
   - Confirm that only plain-text transcripts are transmitted over the network to the LLM API.
   - Confirm that video pixels, audio waveforms, and facial landmark coordinates remain 100% local.

5. **Verify Git Hygiene:**
   - Inspect `.gitignore` to ensure `.env`, SQLite databases (`*.db`, `*.db-wal`), media files (`*.mp4`, `*.wav`), and model weights (`models/`) are excluded.

## Technical Standards
- **Zero Secret Commits:** Even in private repositories, secret leakage is treated as a critical defect.
- **Subprocess Sanitization:** Avoid shell injection vulnerabilities. Always pass arguments to `subprocess` or `asyncio.create_subprocess_exec` as a list of strings, never with `shell=True`.

## Common Mistakes to Avoid
- **Using `shell=True`:** Passing raw user input or file paths to `shell=True` enables command injection.
- **Logging Exception Dumps Containing Keys:** Catching an `httpx.HTTPStatusError` and printing `str(error)` which may include authorization headers in the URL/dump.
- **Assuming Public Means Permissive:** Copying code from public GitHub repos that lack an open-source license.

## Verification Checklist
- [ ] No API keys or tokens exist in source code or committed configs.
- [ ] Request headers are sanitized in all log outputs.
- [ ] Subprocess calls use argument lists without `shell=True`.
- [ ] All third-party dependencies have verified permissive licenses.
- [ ] `.gitignore` prevents committing secrets or media files.

