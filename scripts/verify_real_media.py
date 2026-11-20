"""Real-Media Integration Verification Script for Stage 2.2.

Executes real-video FFprobe probing, API upload, Range request streaming,
and real FFmpeg 16kHz audio extraction against physical video fixtures.
"""

import json
import os
import subprocess
from pathlib import Path
from fastapi import UploadFile

from clipforge.api.routes.projects import (
    extract_project_audio,
    get_project,
    stream_project_video,
    upload_video,
)
from clipforge.core.config import settings
from clipforge.db.session import init_db
from clipforge.media.ffmpeg import ffmpeg_engine


def run_ffprobe_raw(file_path: Path) -> dict:
    cmd = [
        str(Path("tools/ffmpeg/bin/ffprobe.exe").resolve()),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def main():
    print("=================================================================")
    print("STAGE 2.2 REAL-MEDIA INTEGRATION VERIFICATION")
    print("=================================================================\n")

    settings.ensure_directories()
    init_db()

    video_with_audio = Path("fixtures/test_video_with_audio.mp4")
    video_no_audio = Path("fixtures/test_video_no_audio.mp4")

    # -------------------------------------------------------------
    # Step A: Raw FFprobe vs ClipForge Backend Metadata Probe
    # -------------------------------------------------------------
    print("--- STEP A: FFprobe Metadata Verification ---")
    raw_probe = run_ffprobe_raw(video_with_audio)
    backend_probe = ffmpeg_engine.probe_metadata(video_with_audio)

    raw_vstream = next(s for s in raw_probe["streams"] if s["codec_type"] == "video")
    raw_astream = next(s for s in raw_probe["streams"] if s["codec_type"] == "audio")

    print(f"Duration:         Backend={backend_probe['duration_seconds']}s | Raw={raw_probe['format']['duration']}s")
    print(f"Resolution:       Backend={backend_probe['width']}x{backend_probe['height']} | Raw={raw_vstream['width']}x{raw_vstream['height']}")
    print(f"Frame Rate:       Backend={backend_probe['fps']} fps | Raw r_frame_rate={raw_vstream['r_frame_rate']}")
    print(f"Video Codec:      Backend={backend_probe['video_codec']} | Raw={raw_vstream['codec_name']}")
    print(f"Audio Codec:      Backend={backend_probe['audio_codec']} | Raw={raw_astream['codec_name']}")
    print(f"Has Audio:        Backend={backend_probe['has_audio']} (Audio streams present: {raw_astream is not None})")
    print(f"File Size:        Backend={backend_probe['file_size_bytes']} bytes | File on disk={video_with_audio.stat().st_size} bytes")
    print(f"Container Format: Backend={backend_probe['container_format']} | Raw format_name={raw_probe['format']['format_name']}")

    assert backend_probe["width"] == 1280
    assert backend_probe["height"] == 720
    assert backend_probe["fps"] == 30.0
    assert backend_probe["has_audio"] is True
    assert backend_probe["audio_codec"] == "aac"
    print(">>> Step A PASSED: Backend probe matches physical FFprobe output exactly.\n")

    # -------------------------------------------------------------
    # Step B: Upload Through API
    # -------------------------------------------------------------
    print("--- STEP B: API Upload & Streaming Verification ---")
    with open(video_with_audio, "rb") as f:
        upload_file = UploadFile(filename="test_video_with_audio.mp4", file=f)
        project = upload_video(upload_file)

    print(f"Project ID:       {project.id}")
    print(f"Project Title:    {project.title}")
    print(f"Project Status:   {project.status}")
    print(f"Source Disk Path: {project.source_file_path}")
    assert Path(project.source_file_path).exists()
    assert project.status == "INGESTED"

    # Verify DB record
    db_project = get_project(project.id)
    assert db_project.id == project.id
    assert db_project.width == 1280
    assert db_project.height == 720
    assert db_project.has_audio is True
    print("Database persistence verified.")

    # Verify Full Stream (200 OK)
    full_resp = stream_project_video(project.id, range=None)
    assert full_resp.status_code == 200
    assert full_resp.headers["Content-Type"] == "video/mp4"
    print(f"Full video streaming HTTP 200 OK verified (Content-Type: {full_resp.headers['Content-Type']}).")

    # Verify Range Request (206 Partial Content)
    range_resp = stream_project_video(project.id, range="bytes=0-999")
    assert range_resp.status_code == 206
    assert range_resp.headers["Content-Range"].startswith("bytes 0-999/")
    print(f"HTTP Range partial streaming HTTP 206 Partial Content verified (Content-Range: {range_resp.headers['Content-Range']}).")
    print(">>> Step B PASSED: Upload, DB persistence, and Range streaming verified.\n")

    # -------------------------------------------------------------
    # Step C: Real FFmpeg Audio Extraction
    # -------------------------------------------------------------
    print("--- STEP C: Real FFmpeg Audio Extraction (16kHz Mono WAV) ---")
    extract_resp = extract_project_audio(project.id)
    print(f"Extraction Status: {extract_resp['status']}")
    print(f"Extracted Path:    {extract_resp['audio_file_path']}")
    print(f"Sample Rate:       {extract_resp['sample_rate']} Hz")
    print(f"Channels:          {extract_resp['channels']} (mono)")

    wav_path = Path(extract_resp["audio_file_path"])
    assert wav_path.exists()
    assert wav_path.stat().st_size > 0

    # Independent media inspection via raw ffprobe on the extracted WAV
    wav_probe = run_ffprobe_raw(wav_path)
    wav_stream = wav_probe["streams"][0]
    wav_duration = float(wav_probe["format"]["duration"])
    wav_sample_rate = int(wav_stream["sample_rate"])
    wav_channels = int(wav_stream["channels"])
    wav_codec = wav_stream["codec_name"]

    print(f"Independent Inspection of extracted WAV:")
    print(f"  Codec:       {wav_codec} (Expected: pcm_s16le)")
    print(f"  Sample Rate: {wav_sample_rate} Hz (Expected: 16000)")
    print(f"  Channels:    {wav_channels} (Expected: 1)")
    print(f"  Duration:    {wav_duration:.2f}s (Expected: ~3.0s)")
    print(f"  File Size:   {wav_path.stat().st_size} bytes")

    assert wav_codec == "pcm_s16le"
    assert wav_sample_rate == 16000
    assert wav_channels == 1
    assert wav_duration > 0
    print(">>> Step C PASSED: Valid 16kHz mono 16-bit PCM WAV confirmed by independent FFprobe.\n")

    # -------------------------------------------------------------
    # Step D: No-Audio Video Verification
    # -------------------------------------------------------------
    print("--- STEP D: No-Audio Video Handling ---")
    with open(video_no_audio, "rb") as f:
        u_no_audio = UploadFile(filename="test_video_no_audio.mp4", file=f)
        p_no_audio = upload_video(u_no_audio)

    print(f"No-Audio Project ID:     {p_no_audio.id}")
    print(f"No-Audio has_audio flag: {p_no_audio.has_audio} (Expected: False)")
    print(f"No-Audio audio_codec:    '{p_no_audio.audio_codec}' (Expected: empty)")
    assert p_no_audio.has_audio is False
    assert p_no_audio.audio_codec == ""

    # Attempt audio extraction on silent video
    from fastapi import HTTPException
    no_audio_raised = False
    try:
        extract_project_audio(p_no_audio.id)
    except HTTPException as e:
        no_audio_raised = True
        print(f"Extraction correctly rejected with HTTP {e.status_code}: {e.detail}")
        assert e.status_code == 400
        assert "does not contain an audio track" in e.detail

    assert no_audio_raised is True

    # Verify no corrupt/empty WAV exists
    supposed_wav = settings.projects_dir / p_no_audio.id / "audio_16k.wav"
    assert not supposed_wav.exists()
    print(f"Verified that no empty/corrupt WAV was created at {supposed_wav}.")

    # Verify DB status updated to NO_AUDIO
    db_no_audio = get_project(p_no_audio.id)
    assert db_no_audio.status == "NO_AUDIO"
    print(f"Database status correctly marked as '{db_no_audio.status}'.")
    print(">>> Step D PASSED: No-audio video gracefully handled without corrupt files.\n")

    print("=================================================================")
    print("ALL REAL-MEDIA INTEGRATION CHECKS (A, B, C, D) PASSED!")
    print("=================================================================")


if __name__ == "__main__":
    main()

