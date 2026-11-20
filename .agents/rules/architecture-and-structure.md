# Rule: Architecture & Project Structure

## 1. Directory Structure

All ClipForge AI code must reside within the following standardized structure:

```text
clipforge-ai/
├── AGENTS.md                   # Authoritative project instructions
├── .agents/                    # Antigravity customization root
│   ├── rules/                  # Workspace rules
│   ├── skills/                 # Procedural skill runbooks
│   └── agents/                 # Custom subagent definitions
├── clipforge/                  # Core Python backend package
│   ├── core/                   # Configuration, hardware detection, logging, security
│   ├── db/                     # SQLite models, migrations, WAL configuration
│   ├── media/                  # FFmpeg wrapper, audio extraction, scene detection
│   ├── ai/                     # LLM client, prompt templates, word-index validator
│   ├── pipeline/               # Job orchestrator, state machine, SSE broadcaster
│   └── api/                    # FastAPI routes, schemas, dependencies
├── frontend/                   # React + TypeScript + Vite frontend
│   ├── src/
│   │   ├── components/         # Reusable UI components
│   │   ├── views/              # Main workflow views (Dashboard, Review, Settings)
│   │   ├── hooks/              # Custom hooks (SSE stream, video player)
│   │   └── api/                # API client functions
│   └── package.json
├── tests/                      # Automated test suite
│   ├── unit/                   # Fast isolated unit tests
│   └── integration/            # Multi-component pipeline tests
├── clipforge-data/             # Managed local data root (ignored by git)
│   └── projects/{project_id}/  # Project assets, work artifacts, and exports
└── scripts/                    # Maintenance, benchmarking, and verification scripts
```

## 2. Architectural Boundaries

- **Separation of Concerns:** `clipforge/media/` handles binary video/audio manipulation; it must know nothing about HTTP routes. `clipforge/api/` handles HTTP request parsing and response formatting; it delegates all work to `clipforge/pipeline/`.
- **No Uncompressed Video in Python RAM:** High-resolution frames must never be buffered into Python memory. Video operations are delegated to FFmpeg via subprocess calls.
- **Stateless Media Engines:** Media processing utilities must be designed as stateless functions or thin wrappers receiving input file paths and emitting output file paths.
- **Resilient Artifact Pipeline:** Each pipeline stage reads from the previous stage's disk artifact and writes a new artifact:
  1. `01_source.mp4` -> `02_audio_16k.wav`
  2. `02_audio_16k.wav` -> `03_transcript.json`
  3. `03_transcript.json` -> `04_highlights.json`
  4. `04_highlights.json` + `01_source.mp4` -> `05_cuts.json` & `06_crops.json`
  5. `06_crops.json` + `03_transcript.json` -> `07_subtitles.ass`
  6. `07_subtitles.ass` + `01_source.mp4` -> `08_export.mp4`
- **Database Role:** SQLite (configured in WAL mode) stores project metadata, job statuses, candidate clip models, and settings. It does not store large binary blobs.

