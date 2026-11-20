---
name: video-processing
description: >-
  Use this skill when implementing, optimizing, or debugging video manipulation, FFmpeg
  filtergraphs, audio extraction, scene cut detection, active speaker reframing, or video export.
---

# Video Processing & Reframing Skill

This skill governs all video and audio processing operations in ClipForge AI, utilizing FFmpeg, PySceneDetect, and MediaPipe.

## When to Use This Skill
- Implementing or tuning FFmpeg wrappers for audio/video extraction.
- Detecting camera shot cut boundaries with `PySceneDetect`.
- Tracking faces and calculating active speaker crop paths via MediaPipe.
- Generating Advanced SubStation Alpha (`.ass`) karaoke subtitles and burning via `libass`.
- Encoding finished vertical 9:16 MP4 clips.

## Step-by-Step Procedure

1. **Inspect Media Container:**
   - Probe input video metadata using `ffprobe` (width, height, fps, duration, audio channels).
   - Ensure input format is supported (`.mp4`, `.mov`, `.mkv`, `.webm`).

2. **Extract Standardized Audio Stream:**
   - Execute FFmpeg to produce a standardized 16kHz mono 16-bit PCM WAV file:
     ```bash
     ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ac 1 -ar 16000 -y audio_16k.wav
     ```

3. **Segment Camera Shots (`PySceneDetect`):**
   - Use `ContentDetector` on a 2x-downscaled stream to locate visual cut boundaries.
   - Record cut timestamps `[t_0, t_1, ...]`. Crop trajectories must strictly snap across these cuts.

4. **Calculate Active Speaker Crop Window:**
   - Sample frames within each shot at 5 FPS.
   - Detect face bounding boxes via MediaPipe.
   - For multi-face shots, compute Mouth Aspect Ratio (MAR) variance over a 0.6s window to isolate the speaker.
   - Apply Exponential Moving Average (EMA) smoothing intra-shot ($\alpha = 0.15$).
   - Fall back to a balanced center crop if confidence is low or if no faces are present.

5. **Generate Karaoke Subtitles:**
   - Convert Whisper word timings into `.ass` format with `{\k<centiseconds>}` karaoke tags.
   - Style: High-contrast yellow active word (`&H0000FFFF`), white inactive (`&H00FFFFFF`), black outline.

6. **Render Final Export via FFmpeg:**
   - Construct a single-pass filtergraph:
     ```text
     [0:v]crop=w=ih*(9/16):h=ih:x=X_POS:y=0,scale=1080:1920[v_crop];
     [v_crop]ass=subtitles.ass[v_out];
     [0:a]loudnorm=I=-14:LRA=11:TP=-1.5[a_out]
     ```
   - Encode using CPU `libx264`: `-c:v libx264 -preset fast -crf 20 -c:a aac -b:a 192k`.

## Technical Standards & Hardware Constraints
- **Host GPU:** Intel Iris Xe (Integrated). **Do NOT use `h264_nvenc`.** Default to `libx264`.
- **Memory Safety:** Never buffer raw frames in Python RAM. Let FFmpeg handle pixels in C memory.
- **Audio Compliance:** Standardize final audio to -14 LUFS for TikTok and Instagram.

## Common Mistakes to Avoid
- **Panning Across Scene Cuts:** Interpolating crop coordinates across camera changes creates sickening pans. Always snap coordinates at cut points.
- **MoviePy / PIL Rasterization:** Rendering subtitles frame-by-frame in Python causes severe RAM leaks. Always burn via FFmpeg `libass`.
- **Subprocess Deadlocks:** Calling `subprocess.run()` without handling pipe buffers can deadlock FFmpeg. Use `asyncio.create_subprocess_exec()` with proper buffer draining.

## Verification Checklist
- [ ] Extracted audio is strictly 16,000 Hz, mono PCM.
- [ ] PySceneDetect cut list prevents cross-cut panning.
- [ ] Exported MP4 is exactly 1080x1920 resolution.
- [ ] Video playback and audio sync are validated on a test clip.
- [ ] Subprocess cleanly releases file handles on Windows.

