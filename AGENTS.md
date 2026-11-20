# ClipForge AI — Developer & Agent Instructions

Welcome to **ClipForge AI**. This document provides authoritative project instructions, scope boundaries, hardware constraints, and agent operational standards for all AI agents and human contributors working on this codebase.

---

## 1. Project Overview & Vision

ClipForge AI is a **local-first, desktop-optimized AI video clipping application** designed for content creators, video editors, and social media managers. It transforms long-form video content (talks, podcasts, tutorials, interviews) into high-retention 9:16 vertical short clips optimized for TikTok, Instagram Reels, and YouTube Shorts.

### Core Philosophy
1. **Local-First Processing:** Heavy media processing, audio extraction, transcription, computer-vision reframing, and final rendering execute **100% locally** on the user's workstation. User video and audio never leave the local machine.
2. **External Intelligence Boundary:** An external LLM API is used strictly for tasks requiring semantic intelligence: highlight discovery, viral scoring, hook generation, and title/description copywriting. The LLM receives text transcripts only.
3. **Quality Over Quantity:** The application prioritizes extracting a few coherent, high-impact moments with clear hooks and payoffs rather than flooding the user with arbitrary transcript snippets.
4. **Resilient Artifact Pipeline:** Processing stages produce immutable disk artifacts in `projects/{project_id}/work/`. If any step fails or is interrupted, the job resumes from the last completed stage.

---

## 2. Approved MVP Scope

To guarantee rapid execution, stability, and high quality, the MVP scope is strictly disciplined:

### In Scope for MVP:
1. **Local Video Ingest:** Drag-and-drop / file selector for `.mp4`, `.mov`, `.mkv`, and `.webm`. Container metadata inspection via `ffprobe`.
2. **Audio Extraction:** Fast extraction of standardized 16kHz 16-bit mono PCM WAV files via FFmpeg.
3. **Word-Level Transcription:** Local speech-to-text using `faster-whisper` with Silero VAD silence filtering, generating word-level timestamps and indices.
4. **AI Highlight Discovery:** External LLM integration requesting candidate clips defined by `start_word_index` and `end_word_index`.
5. **Deterministic Boundary Validation:** A 4-rule validation engine enforcing index bounds, sentence completeness snapping, duration constraints (15s–90s), and silence thresholding.
6. **Basic Vertical 9:16 Cropping:** Visual face tracking via MediaPipe with shot-cut protection via PySceneDetect and balanced center-crop fallback.
7. **Basic Synchronized Captions:** Advanced SubStation Alpha (`.ass`) karaoke word highlighting burned directly via FFmpeg's `libass`.
8. **High-Quality MP4 Export:** Hardware/CPU-adaptive video encoding (`libx264` default on this machine) with EBU R128 loudness normalization (-14 LUFS).
9. **Settings & Connection Tester:** Configuration for LLM API base URL, API key, model name, and protocol (`openai_compatible` vs. `anthropic`).

### Deferred to Post-MVP (Do Not Implement in MVP):
- YouTube downloading via `yt-dlp` (prioritize local file workflows first).
- Complex multi-speaker split-screen layouts.
- Generative AI b-roll or avatar synthesis.
- Direct social media account integration or cloud publishing.

---

## 3. Host Hardware Profile & Resource Constraints

All development and execution must be tailored for the user's specific laptop:

| Specification | Parameter | Development Constraint |
| :--- | :--- | :--- |
| **CPU** | Intel Core i7-1255U (10 cores: 2 P-cores, 8 E-cores, 12 threads) | Multi-threading must be controlled; do not starve the OS. |
| **RAM** | 16 GB DDR4/DDR5 | Keep peak memory under 6 GB during heavy operations. |
| **GPU** | Intel Iris Xe Graphics (Integrated) | **No NVIDIA CUDA / NVENC.** Do not assume GPU acceleration. Use CPU `int8` for Whisper and `libx264` for FFmpeg. |
| **Free Storage** | **~22 GB free on a 477 GB SSD** | **STORAGE CONSTRAINED.** Clean up temporary files; do not download models $>1\text{ GB}$; warn user before large allocations. |
| **OS** | Windows 11 (64-bit) | Use Windows-compatible paths, subprocess flags, and tools. |

### Operational Hardware Rules:
- **Default Transcription Config:** `faster-whisper` running on `device="cpu"` with `compute_type="int8"`. Default to `base` (~140MB) or `small` (~460MB) model.
- **Never Download Large Models Unannounced:** Do not download `large-v3` (~1.5GB) without explicit user consent.
- **FFmpeg Encoding:** Use CPU encoding: `-c:v libx264 -preset fast -crf 20 -c:a aac -b:a 192k`.
- **Sequential Execution Only:** Never run transcription, scene detection, face tracking, and video export at the same time.
- **Disk Protection:** Never delete personal files. Clean only managed scratch files inside `clipforge-data/` or `projects/{id}/temp/`.

---

## 4. Agent Communication & Workflow Protocol

All autonomous agents must adhere to the following operational standards:

### 4.1 Strict Phase Discipline
- **NO IMPLEMENTATION PHASE BEGINS WITHOUT EXPLICIT USER APPROVAL.**
- Phase 1 (Research & Architecture) is complete.
- We are currently in workspace preparation.
- Do not implement Phase 2 application code until the user explicitly requests it.

### 4.2 Standard 9-Step Development Cycle
Every development cycle must follow this repeatable process:
1. **Understand:** Read the user's prompt carefully and identify core objectives.
2. **Inspect:** Examine existing files, schemas, and tests before making modifications.
3. **Assess:** Identify risks, edge cases, and hardware implications.
4. **Propose:** Present a concise implementation plan with proposed file changes.
5. **Seek Approval:** If the proposed change alters architecture or adds dependencies, ask the user first.
6. **Implement:** Execute modifications in small, focused, verifiable steps.
7. **Test & Verify:** Run targeted unit or integration tests to prove correctness.
8. **Inspect Results:** Examine actual tool output, log lines, and generated files.
9. **Report:** Deliver a concise summary of modified files, test outputs, known limitations, and next steps.

### 4.3 Agent Collaboration & Handover
- The **Main Agent** acts as the primary coordinator, interacting with the user and orchestrating work.
- Specialized subagents (`backend-architect`, `media-processing-engineer`, `frontend-engineer`, `qa-security-reviewer`) may be invoked for isolated, deep-focus tasks.
- Subagents must report clean summaries back to the coordinator.
- Avoid running multiple heavy subagents concurrently to protect laptop CPU and RAM.

---

## 5. Security & Secret Management

- **API Keys:** Never hardcode API keys or credentials in any file, test script, or prompt.
- **Environment Isolation:** Read credentials strictly from `.env` or system environment variables (`CLIPFORGE_LLM_API_KEY`).
- **Secret Scrubbing:** All logging utilities must sanitize request headers and payloads, masking `Authorization` and `x-api-key`.
- **Git Hygiene:** Verify `.gitignore` before every commit. Never commit `.env`, media files (`.mp4`, `.wav`), or SQLite databases.

---

## 6. Specialized Workspace Rules Directory

To maintain focus and prevent context bloat in this master instruction file, detailed technical standards are modularized under `.agents/rules/`.

> [!IMPORTANT]
> **Mandatory Rule Reading:** Before implementing, refactoring, or reviewing any task, agents **MUST read the corresponding rule file** listed below. Do not proceed with code changes without consulting the applicable rule.

| Specialized Rule File | Scope & Domain | When Agents Must Read |
| :--- | :--- | :--- |
| [.agents/rules/architecture-and-structure.md](file:///c:/Users/25194/Desktop/New%20folder/work/clipforge-ai/.agents/rules/architecture-and-structure.md) | System boundaries, directory layout, disk artifact pipeline, SQLite role. | When creating new directories, defining data flows, or modifying module boundaries. |
| [.agents/rules/python-fastapi.md](file:///c:/Users/25194/Desktop/New%20folder/work/clipforge-ai/.agents/rules/python-fastapi.md) | Python 3.11+ standards, FastAPI async routes, Pydantic v2 schemas, error handling. | When writing backend endpoints, Pydantic models, database operations, or background workers. |
| [.agents/rules/frontend-standards.md](file:///c:/Users/25194/Desktop/New%20folder/work/clipforge-ai/.agents/rules/frontend-standards.md) | React 18+, TypeScript strict mode, Tailwind dark theme, SSE streams, player UI. | When creating or modifying UI components, styling, state management, or video preview views. |
| [.agents/rules/testing-and-verification.md](file:///c:/Users/25194/Desktop/New%20folder/work/clipforge-ai/.agents/rules/testing-and-verification.md) | Pytest suites, mock LLM fixtures, async endpoint testing, verification checklists. | Before declaring any implementation task complete, and when authoring automated tests. |
| [.agents/rules/security-and-data.md](file:///c:/Users/25194/Desktop/New%20folder/work/clipforge-ai/.agents/rules/security-and-data.md) | Secret redaction, zero hardcoded keys, `.env` isolation, user data privacy. | When handling API credentials, configuring logging, or vetting third-party dependencies. |
| [.agents/rules/media-and-hardware.md](file:///c:/Users/25194/Desktop/New%20folder/work/clipforge-ai/.agents/rules/media-and-hardware.md) | Intel i7-1255U & Iris Xe constraints, CPU int8 Whisper, libx264, disk limits. | When writing FFmpeg commands, Whisper wrappers, reframing logic, or video export jobs. |

