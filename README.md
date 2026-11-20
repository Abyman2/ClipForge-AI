# ClipForge AI

> **Local-First, Desktop-Optimized AI Video Clipping Application**  
> Transform long-form videos (talks, podcasts, tutorials, interviews) into high-retention 9:16 vertical short clips optimized for TikTok, Instagram Reels, and YouTube Shorts.

---

## 1. Core Architectural Principles

1. **Local-First Media Processing:** Audio extraction, speech-to-text transcription, shot-cut detection, active speaker reframing, and final 1080x1920 MP4 rendering execute **100% locally** on the user's workstation.
2. **External Intelligence Boundary:** An external LLM API is used strictly for tasks requiring semantic intelligence (highlight discovery, viral scoring, hook copywriting). The LLM receives text transcripts only.
3. **Hardware-Adaptive & Storage-Conscious:** Specifically optimized for standard consumer laptops (Intel Core i7-1255U, Iris Xe integrated graphics, CPU `int8` Whisper, and `libx264` encoding) with automatic disk headroom monitoring.

---

## 2. Project Structure

```text
clipforge-ai/
├── AGENTS.md                   # Authoritative developer & agent standards
├── ARCHITECTURE.md             # System architecture specification
├── RESEARCH_REPORT.md          # Open-source technical research report
├── TECH_STACK_DECISIONS.md     # Rationale for core technology choices
├── IMPLEMENTATION_ROADMAP.md   # Six-phase test-driven implementation plan
├── RISKS_AND_LIMITATIONS.md    # Risk catalog, failure modes & mitigations
├── CUSTOMIZATION_VERIFICATION.md # Verification gate audit report
│
├── clipforge/                  # Python Backend Core
│   ├── core/                   # Configuration, hardware profiling, secret logging
│   │   ├── config.py
│   │   ├── hardware.py
│   │   └── logging.py
│   ├── db/                     # SQLite WAL mode session & data schemas
│   │   ├── session.py
│   │   └── models.py
│   ├── media/                  # FFmpeg wrappers & media interfaces
│   │   └── ffmpeg.py
│   ├── ai/                     # Provider-independent LLM adapters & prompt schemas
│   │   └── adapter.py
│   ├── api/                    # FastAPI application & route controllers
│   │   ├── app.py
│   │   └── routes/
│   │       └── health.py
│   └── main.py                 # Backend CLI server runner
│
├── frontend/                   # React + TypeScript + Vite + Tailwind UI
│   ├── src/
│   │   ├── components/         # Header, Sidebar, StatusCard
│   │   ├── types/              # TypeScript interface definitions
│   │   ├── App.tsx             # Main dashboard view & telemetry monitor
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── tests/                      # Automated Test Suite
│   └── unit/                   # Fast, offline unit tests
│       ├── test_config.py
│       ├── test_db.py
│       ├── test_health.py
│       ├── test_media_interface.py
│       └── test_ai_adapter.py
│
├── .agents/                    # Antigravity Customizations
│   ├── rules/                  # Modular workspace rules
│   ├── skills/                 # Procedural skill runbooks
│   └── agents/                 # Specialized subagent definitions
│
├── .env.example                # Example environment variables
└── requirements.txt            # Python dependencies
```

---

## 3. Quickstart & Execution Guide

### Prerequisites
- Python 3.11 or 3.12 (64-bit)
- Node.js 18+ and npm 9+
- Windows 11 (or macOS / Linux)

### Backend Setup
1. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```
2. **Install Backend Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run Automated Tests:**
   ```bash
   pytest tests/ -v
   ```
4. **Start Backend Server:**
   ```bash
   python -m clipforge.main
   ```
   *The FastAPI server will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000), with interactive Swagger documentation at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).*

### Frontend Setup
1. **Install Frontend Dependencies:**
   ```bash
   cd frontend
   npm install
   ```
2. **Build for Production:**
   ```bash
   npm run build
   ```
3. **Start Development Server:**
   ```bash
   npm run dev
   ```
   *The React dashboard will be available at [http://localhost:5173](http://localhost:5173).*

---

## 4. Current Status: Stage 2.1 Complete

- **Backend:** FastAPI application initialized with SQLite in Write-Ahead Logging (WAL) mode.
- **Diagnostics:** `/api/health` endpoint live, reporting system telemetry, CPU cores, free disk space, and media tools.
- **Frontend:** React 18, TypeScript, and Tailwind CSS dark-themed dashboard shell initialized.
- **Testing:** Unit test suite covering configuration, database initialization, health endpoints, FFmpeg interface, and AI adapter.
