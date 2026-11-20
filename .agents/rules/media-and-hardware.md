# Rule: Media Processing & Hardware Constraints

## 1. Host Hardware Constraints

ClipForge AI is optimized for the user's specific laptop:
- **CPU:** Intel Core i7-1255U (10 cores: 2 P-cores, 8 E-cores, 12 threads)
- **RAM:** 16 GB DDR4/DDR5
- **GPU:** Intel Iris Xe Integrated Graphics (No discrete NVIDIA GPU; no CUDA; no NVENC)
- **Storage:** ~22 GB free disk space on a 477 GB SSD (**STORAGE CONSTRAINED**)
- **OS:** Windows 11 (64-bit)

## 2. Processing & Resource Allocation Rules

- **CPU-First Execution:**
  - Configure `faster-whisper` with `device="cpu"` and `compute_type="int8"`.
  - Default model size is `base` (~140MB) or `small` (~460MB). Never download `large-v3` (~1.5GB) without explicit user authorization.
  - Video encoding must default to CPU `libx264`: `-c:v libx264 -preset fast -crf 20 -c:a aac -b:a 192k`.
- **Sequential Pipeline Execution:**
  - Pipeline stages must execute strictly one after another:
    `Ingest -> Audio Extraction -> Transcription -> Highlight Discovery -> Reframing -> Export`
  - Never run transcription, scene detection, and FFmpeg rendering concurrently on the same machine.
- **Memory Protection:**
  - High-resolution video frames must NEVER be decoded into Python NumPy/PIL memory arrays.
  - Subtitle burning and cropping must occur within the FFmpeg C-level filtergraph (`crop`, `scale`, `ass`).
- **Storage Management:**
  - Never automatically delete user files or non-project files to free space.
  - Manage all intermediate pipeline files inside `projects/{id}/work/`.
  - Provide an explicit project deletion / cache cleanup utility in the UI to allow users to reclaim disk space safely.
- **Subprocess Safety:**
  - Always invoke FFmpeg and external binaries with timeouts and non-blocking asynchronous wrappers (`asyncio.create_subprocess_exec`).
  - Capture both `stdout` and `stderr` to prevent buffer deadlocks.

