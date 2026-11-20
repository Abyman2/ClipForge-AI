---
name: transcription
description: >-
  Use this skill when implementing, configuring, or testing speech-to-text transcription
  using faster-whisper, Silero VAD, word-level timestamping, and transcript indexing.
---

# Speech-to-Text Transcription Skill

This skill governs the local transcription engine in ClipForge AI using `faster-whisper` (CTranslate2) with Silero Voice Activity Detection (VAD).

## When to Use This Skill
- Configuring or wrapping `faster-whisper` inference.
- Implementing automatic hardware detection and CPU `int8` fallback.
- Extracting word-level timestamps and building `transcript.json`.
- Benchmarking transcription latency and memory consumption.

## Step-by-Step Procedure

1. **Probe System Compute Profile:**
   - Check CUDA device count via `ctranslate2.get_cuda_device_count()`.
   - On the host machine (Intel Core i7-1255U, Iris Xe), automatically configure:
     - `device = "cpu"`
     - `compute_type = "int8"`
     - `model_size = "base"` (or `"small"` if requested)
     - `cpu_threads = 4` (prevent starving the OS)

2. **Load Whisper Model with Caching:**
   - Initialize `WhisperModel` pointing to a local cache directory (`clipforge-data/models/`).
   - Warn the user if the requested model needs to be downloaded for the first time.

3. **Execute Transcription with Silero VAD:**
   - Execute transcription on the standardized 16kHz WAV file:
     ```python
     segments, info = model.transcribe(
         audio_path,
         beam_size=5,
         word_timestamps=True,
         vad_filter=True,
         vad_parameters=dict(min_silence_duration_ms=500),
     )
     ```

4. **Build Indexed Word Structure:**
   - Iterate over words and assign a zero-based global integer index to every word.
   - Build standardized `transcript.json`:
     ```json
     {
       "language": "en",
       "duration": 182.4,
       "words": [
         {"index": 0, "word": "Welcome", "start": 0.24, "end": 0.72},
         {"index": 1, "word": "to", "start": 0.74, "end": 0.88}
       ],
       "segments": [
         {"id": 0, "start": 0.24, "end": 3.80, "text": "Welcome to ClipForge...", "start_word": 0, "end_word": 5}
       ]
     }
     ```

5. **Persist Artifact & Record State:**
   - Write `transcript.json` to `projects/{project_id}/work/03_transcript.json`.
   - Update SQLite project status to `TRANSCRIPTION_COMPLETED`.

## Technical Standards
- **Model Tiers:** `base` (~140MB) is default; `small` (~460MB) is optional for higher accuracy. Do NOT load `large-v3` on this CPU.
- **Word Timestamps:** `word_timestamps=True` is mandatory; highlight discovery and karaoke subtitles depend on it.
- **VAD Filtering:** `vad_filter=True` is mandatory to eliminate hallucinated text loops during pauses.

## Common Mistakes to Avoid
- **Using openai/whisper:** Standard PyTorch Whisper is 4x slower and consumes excessive RAM. Always use `faster-whisper`.
- **Floating-Point Drift:** Rounding word timestamps prematurely. Keep timestamps as native floats until subtitle export.
- **Uncontrolled Threads:** Setting `cpu_threads` to max core count (12), which locks the user's laptop UI. Cap to 4–6 threads.

## Verification Checklist
- [ ] Model loads cleanly on CPU with `int8` quantization.
- [ ] Word indices form a continuous sequence from $0$ to $N-1$.
- [ ] Timestamps are strictly monotonic ($start < end$).
- [ ] Silero VAD successfully skips long silent gaps.
- [ ] Output `transcript.json` validates against the Pydantic schema.

