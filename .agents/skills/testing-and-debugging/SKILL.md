---
name: testing-and-debugging
description: >-
  Use this skill when writing unit tests, running integration suites, debugging pipeline
  failures, or diagnosing Windows 11 performance bottlenecks in ClipForge AI.
---

# Testing & Debugging Skill

This skill governs testing standards, automated test execution, and systematic debugging procedures across the ClipForge AI application.

## When to Use This Skill
- Writing unit tests for Pydantic validators, boundary snappers, or FFmpeg filters.
- Running the `pytest` test suite before completing any implementation task.
- Diagnosing failed pipeline jobs, FFmpeg exit codes, or audio synchronization drift.
- Profiling memory consumption and CPU thread usage on Windows 11.

## Step-by-Step Testing Procedure

1. **Write Isolated Unit Tests First:**
   - Place unit tests in `tests/unit/`.
   - Test core algorithms (word-index boundary snapping, sentence completion, duration calculation) using pure Python data structures without disk I/O.

2. **Write Integration Tests with Synthetic Fixtures:**
   - Place integration tests in `tests/integration/`.
   - Use small synthetic fixtures:
     - A 2-second synthetic 16kHz WAV file generated via `scipy.io.wavfile` or FFmpeg.
     - Mocked LLM JSON responses (never call real external APIs in automated tests).

3. **Execute Test Suite via Pytest:**
   - Run tests using the standard test command:
     ```bash
     pytest tests/ -v
     ```
   - Inspect stdout/stderr for any unexpected warnings or unhandled exceptions.

4. **Debugging Pipeline Failures:**
   - **Step 1: Check Job Database Record:** Inspect the `Job.error_message` and `Job.log_output` fields in SQLite.
   - **Step 2: Inspect Disk Artifacts:** Check `projects/{id}/work/` to see which stage failed to produce its output file.
   - **Step 3: Reproduce FFmpeg Command:** Run the exact FFmpeg command logged by the wrapper in a terminal to inspect raw C-level error codes.

5. **Diagnosing Performance & Memory Bottlenecks:**
   - Monitor system RAM and CPU usage during pipeline runs.
   - Verify that `faster-whisper` is running in `int8` mode and that FFmpeg is using `libx264` with `-preset fast`.

## Technical Standards
- **Zero Cost Testing:** Never trigger real external LLM API calls during automated tests.
- **Deterministic Assertions:** Never use randomized sleep timers in tests; use explicit polling or event flags with timeouts.
- **Cleanup:** Test fixtures must use `tmp_path` to avoid leaving temporary files on disk.

## Common Mistakes to Avoid
- **Committing Media Blobs:** Checking large video files into the Git repository for testing.
- **Skipping Verification:** Declaring a task done without actually running `pytest`.
- **Ignoring Windows Path Separators:** Using hardcoded forward slashes or backslashes without `pathlib.Path`.

## Verification Checklist
- [ ] All tests run and pass cleanly via `pytest`.
- [ ] No external API requests were made during test runs.
- [ ] Temporary files were created in `tmp_path` and cleaned up.
- [ ] Error handling captures full tracebacks into the job log.

