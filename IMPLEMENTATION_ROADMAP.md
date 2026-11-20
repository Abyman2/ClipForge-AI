# ClipForge AI — Technical Implementation Roadmap

**Author:** ClipForge Architecture & Engineering Team  
**Date:** November 2026  
**Document Version:** 1.1.0 (Post-Validation Revision)  
**Phase:** Phase 1 — Research & Planning

---

## 1. Roadmap Overview & Phasing

ClipForge AI development is divided into **six disciplined, test-driven phases**. The MVP focuses strictly on rock-solid local execution and core clipping workflows before introducing decorative UI features or secondary remote integrations.

```mermaid
flowchart LR
    P1["Phase 1<br>Research & Architecture<br>(Completed)"] --> P2["Phase 2<br>Foundation & Media Engine<br>(Next Phase)"]
    P2 --> P3["Phase 3<br>AI Discovery & Validation"]
    P3 --> P4["Phase 4<br>Reframing & Subtitle Engine"]
    P4 --> P5["Phase 5<br>FastAPI Backend & Pipeline"]
    P5 --> P6["Phase 6<br>Frontend UI & End-to-End MVP"]
```

---

## 2. Detailed Phase Breakdown

### Phase 1: Research, Architecture & Validation (COMPLETED)
- **Objective:** Deep technical investigation of repositories, license auditing, active speaker analysis, word-index validation rules, hardware profiling, and comprehensive documentation.
- **Deliverables:**
  - `RESEARCH_REPORT.md` (v1.1.0)
  - `ARCHITECTURE.md` (v1.1.0)
  - `TECH_STACK_DECISIONS.md` (v1.1.0)
  - `IMPLEMENTATION_ROADMAP.md` (v1.1.0)
  - `RISKS_AND_LIMITATIONS.md` (v1.1.0)
  - `.gitignore` (security & media rules)
- **Status:** Complete. Awaiting user approval to start Phase 2.

---

### Phase 2: Core Media Processing Foundation & Audio Pipeline (IN PROGRESS)
- **Objective:** Implement the local media processing foundation capable of validating video files, probing hardware, extracting clean audio, and generating word-level timestamped transcripts on Windows 11.
- **Target MVP Scope:** Local video files only (`.mp4`, `.mov`, `.mkv`, `.webm`).
- **Implementation Status:**
  - [x] **Stage 2.1: Foundation & Project Scaffold (COMPLETED):**
    - FastAPI backend with Pydantic v2 schemas and SQLite WAL mode.
    - React + TypeScript + Tailwind dark-theme dashboard with Vite proxy.
    - Hardware auto-detection subsystem (`clipforge/core/hardware.py`) targeting Intel i7-1255U CPU and Iris Xe.
  - [x] **Stage 2.2: Video Ingestion & Portable FFmpeg Engine (COMPLETED):**
    - Portable BtbN FFmpeg LGPL Win64 build installed in `tools/ffmpeg/bin/`.
    - Magic-byte validation, media metadata inspection via `ffprobe`, chunked streaming video preview.
    - Standardized 16kHz 16-bit mono PCM WAV extraction.
    - Documentation finalized in `docs/FFMPEG_SETUP.md`.
  - [x] **Stage 2.3: Speech-to-Text Transcription Engine (COMPLETED):**
    - `faster-whisper` (CTranslate2 `int8` on CPU, 4 threads, `tiny` model cached in `models/whisper/`).
    - Silero VAD silence filtering and word-level timestamping.
    - Sequential 0-indexed contiguous word indexing (`index: 0..N-1`).
    - Dual persistence: structured disk artifact `projects/{id}/transcript.json` and SQLite `transcripts` table.
    - API endpoints: `POST /api/projects/{id}/transcribe`, `GET /api/projects/{id}/transcription-status`, `GET /api/projects/{id}/transcript`.
    - Frontend transcript inspector with language detection badge, segment timestamps, and interactive word badge inspector.
    - Verified real-speech benchmark: RTF 0.369x (2.71x faster than real time), 74.58 MB model size, 9.63 GB free disk space.
  - [ ] **Stage 2.4: AI Highlight Discovery & Validation Engine (NEXT STAGE):**
    - External LLM integration requesting candidate clips defined by start/end word indices.
    - 4-rule deterministic boundary validator.

---

### Phase 3: Provider-Independent AI Layer & Highlight Discovery
- **Objective:** Build the protocol-agnostic LLM integration layer and the highlight discovery engine with strict post-LLM validation.
- **Implementation Sequence:**
  1. **Universal LLM Client (`clipforge/ai/client.py`):**
     - Configurable via `LLMConfig` (`api_base_url`, `api_key`, `model_name`, `protocol_type`, `timeout`, `max_retries`).
     - Protocol switcher:
       - `openai_compatible`: Formats to `/v1/chat/completions` with `Bearer` header.
       - `anthropic`: Formats to `/v1/messages` with `x-api-key` and `anthropic-version`.
     - Exponential backoff with jitter on HTTP 429/503.
     - In-memory secret scrubbing filter for headers and payloads.
     - Token accounting per request and cumulative session totals.
  2. **Transcript Chunker (`clipforge/ai/chunker.py`):**
     - Sliding window chunking (15-minute blocks with 2-minute overlap) for long videos.
  3. **Highlight Discovery Engine (`clipforge/ai/prompts.py`):**
     - Structured prompt requesting self-contained moments with hooks, payoffs, and word indices.
     - Robust JSON extractor stripping markdown fences and repairing truncated payloads.
  4. **Word-Index Validation Subsystem (`clipforge/ai/validator.py`):**
     - **Rule 1:** Index range and monotonicity check ($0 \le \text{start} < \text{end} < N$).
     - **Rule 2:** Sentence completeness snapping (snap backward/forward to terminal punctuation or pauses).
     - **Rule 3:** Physical duration enforcement ($15.0\text{s} \le \Delta T \le 90.0\text{s}$).
     - **Rule 4:** Dead-air threshold check (max silence gap $< 3.0\text{s}$).
     - Output verified physical timestamps `(start_time, end_time)`.
- **Testing Strategy:**
  - Mocked HTTP tests verifying protocol serialization and retry logic.
  - Unit tests feeding malformed, inverted, and out-of-bounds indices into `WordIndexValidator` to ensure all rules trigger correctly.
- **Definition of Done:** Given a `transcript.json`, the engine outputs verified candidate clips with valid physical timestamps derived strictly from word indices.

---

### Phase 4: Shot Detection, Active Speaker Reframing & Subtitle Engine
- **Objective:** Convert 16:9 landscape footage into visually balanced 9:16 vertical video with smooth face-centered reframing and synchronized karaoke subtitles.
- **Implementation Sequence:**
  1. **Scene Cut Detection (`clipforge/media/scenes.py`):**
     - `PySceneDetect` wrapper with `ContentDetector` on 2x downscaled video.
     - Generates timestamped cut boundary lists.
  2. **Active Speaker Reframer (`clipforge/media/reframe.py`):**
     - MediaPipe Face Detection worker sampling frames at 5 FPS within shot segments.
     - Multi-face analysis: MediaPipe Face Mesh Lip Landmarks to compute Mouth Aspect Ratio (MAR) variance over a 0.6s window.
     - Exponential Moving Average (EMA) smoothing intra-shot.
     - Hard reset of crop coordinates at scene cuts (zero interpolation across cuts).
     - Minimum dwell time (2.5s) and center-crop fallback.
  3. **Karaoke Subtitle Generator (`clipforge/media/subtitles.py`):**
     - Generate Advanced SubStation Alpha (`.ass`) file with `{\k<centiseconds>}` karaoke tags from Whisper word timings.
     - High-visibility styling preset (yellow active word, white inactive word, black outline).
  4. **Video Exporter (`clipforge/media/export.py`):**
     - Single-pass FFmpeg filtergraph combining crop, scale to 1080x1920, `ass` subtitle burning, and audio `loudnorm` (-14 LUFS).
     - Hardware encoder detection (`h264_nvenc` with fallback to `libx264`).
- **Testing Strategy:**
  - Visual verification tests confirming crop windows remain centered and do not pan across shot cuts.
  - Subtitle audio synchronization tests.
- **Definition of Done:** A candidate clip definition renders into a complete 1080x1920 MP4 vertical video with centered speaker and synchronized captions.

---

### Phase 5: FastAPI Backend, SQLite WAL & Job Pipeline
- **Objective:** Assemble all media and AI engines behind an asynchronous REST API with real-time SSE progress streaming.
- **Implementation Sequence:**
  1. SQLite database setup with Write-Ahead Logging (WAL) and Pydantic schemas.
  2. Job orchestrator managing sequential stages: `INGESTING` -> `TRANSCRIBING` -> `DISCOVERING` -> `REVIEW_READY` -> `EXPORTING` -> `COMPLETED`.
  3. Stage resumption logic reading disk artifacts from `projects/{id}/work/`.
  4. Server-Sent Events (SSE) router streaming progress percentage and log messages.
  5. REST routers: Project CRUD, upload handler, highlight discovery trigger, clip settings, export trigger.
- **Testing Strategy:**
  - API endpoint integration tests using `httpx.AsyncClient`.
  - Process cancellation test verifying clean termination of FFmpeg child processes.
- **Definition of Done:** Full backend operational and accessible via Swagger UI (`/docs`) with real-time SSE streaming.

---

### Phase 6: Frontend UI & End-to-End System Integration
- **Objective:** Deliver a modern dark-themed React/TypeScript UI for project management, video inspection, clip review, and export.
- **Implementation Sequence:**
  1. Vite + React + TypeScript + Tailwind CSS scaffold.
  2. Video Upload & Project Dashboard.
  3. Transcription Progress & Interactive Transcript Viewer.
  4. Highlight Review & Selection Grid (scores, hooks, titles).
  5. Dual-Player Video Review Studio (16:9 source vs. 9:16 vertical crop preview).
  6. Subtitle styling controls and one-click MP4 export.
  7. Settings view for LLM API credentials and hardware profile inspection.
- **Testing Strategy:**
  - End-to-end user journey test: Upload video -> View transcript -> Discover clips -> Review & customize -> Export MP4.
- **Definition of Done:** A user can upload a local video and export high-quality vertical clips entirely through the UI without technical expertise.

---

## 3. Unresolved Decisions & Assumptions

The following items are explicitly tracked as open decisions or engineering assumptions:

| Category | Item / Assumption | Current Working Assumption | Impact / Next Step |
| :--- | :--- | :--- | :--- |
| **API Provider** | Specific external LLM provider & gateway unknown. | System assumes a standard HTTP endpoint supporting either Anthropic `/v1/messages` or OpenAI `/v1/chat/completions`. | Solved via configurable `protocol_type` and custom base URL. Final testing requires actual gateway credentials. |
| **Hardware** | Target user machine compute power is unknown. | Assumes a typical Windows 11 laptop with 8GB–16GB RAM and CPU-only or entry-level GPU. | Mitigated by automated hardware detection, `int8` quantization, and configurable model sizes (`base`/`small`). |
| **YouTube Ingestion**| YouTube stream downloading (`yt-dlp`) reliability. | Assumed secondary to local video upload for MVP. | Local file upload is prioritized in MVP. `yt-dlp` deferred to Phase 2 extension / Phase 7. |
| **Active Speaker** | Acoustic speaker diarization (`pyannote`) is unusable natively on Windows 11 without WSL2. | Assumes visual Lip Motion (MAR) + Shot Cut Detection is sufficient for 90%+ of standard creator videos. | If multi-speaker edge cases demand higher precision post-MVP, explore containerized diarization or lightweight ONNX models. |
| **Desktop Packaging**| Web browser UI vs. native desktop window (Electron/Tauri). | Assumes local browser UI (`localhost:8000`) for MVP speed and simplicity. | Backend/frontend are strictly decoupled, allowing immediate packaging into Tauri or Electron post-MVP. |
