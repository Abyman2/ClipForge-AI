"""Benchmark and verification script for faster-whisper on Intel CPU int8."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clipforge.core.config import settings
from clipforge.core.logging import logger
from clipforge.media.transcribe import TranscriptionEngine


def generate_speech_fixture(output_raw: Path) -> Path:
    """Generate high-clarity speech WAV using Windows System.Speech."""
    output_raw.parent.mkdir(parents=True, exist_ok=True)
    ps_cmd = (
        f"Add-Type -AssemblyName System.Speech; "
        f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Rate = 0; "
        f"$s.SetOutputToWaveFile('{output_raw.resolve()}'); "
        f"$s.Speak('Welcome to ClipForge AI, the local desktop video clipping application. "
        f"We extract high impact moments and vertical video clips with zero cloud dependencies.'); "
        f"$s.Dispose();"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
    return output_raw


def convert_to_16k_mono(input_wav: Path, output_16k: Path) -> Path:
    """Standardize WAV to 16kHz 16-bit Mono PCM using local FFmpeg."""
    ffmpeg_exe = Path("tools/ffmpeg/bin/ffmpeg.exe").resolve()
    if not ffmpeg_exe.exists():
        ffmpeg_exe = "ffmpeg"
    cmd = [
        str(ffmpeg_exe),
        "-y",
        "-i", str(input_wav.resolve()),
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(output_16k.resolve()),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_16k


def run_benchmark():
    fixtures_dir = Path("fixtures")
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    raw_wav = fixtures_dir / "speech_synth_raw.wav"
    speech_16k = fixtures_dir / "speech_benchmark_16k.wav"

    print("--- 1. Generating Speech Fixture ---")
    generate_speech_fixture(raw_wav)
    convert_to_16k_mono(raw_wav, speech_16k)
    print(f"Generated 16kHz WAV at {speech_16k} ({speech_16k.stat().st_size} bytes)")

    # Check free disk space before model download
    _, _, free_before = shutil.disk_usage("C:\\")
    free_before_gb = free_before / (1024**3)
    print(f"C: Drive Free Space Before: {free_before_gb:.2f} GB")

    print("\n--- 2. Initializing & Downloading faster-whisper (tiny int8) ---")
    engine = TranscriptionEngine(
        model_size="tiny",
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
        download_root=settings.whisper_model_dir,
    )

    download_start = time.perf_counter()
    model = engine.get_model()
    download_elapsed = time.perf_counter() - download_start
    print(f"Model loaded / verified in {download_elapsed:.2f}s")

    # Check model directory size
    model_dir = settings.whisper_model_dir
    model_size_bytes = sum(f.stat().st_size for f in model_dir.glob("**/*") if f.is_file())
    model_size_mb = model_size_bytes / (1024 * 1024)
    print(f"Whisper Model Cache Size: {model_size_mb:.2f} MB ({model_size_bytes} bytes)")

    _, _, free_after_download = shutil.disk_usage("C:\\")
    print(f"C: Drive Free Space After Download: {free_after_download / (1024**3):.2f} GB")

    print("\n--- 3. Running Benchmark Transcription ---")
    t0 = time.perf_counter()
    result = engine.transcribe_file(speech_16k, language="en")
    t1 = time.perf_counter()

    inference_duration = t1 - t0
    audio_duration = result["duration"]
    rtf = inference_duration / audio_duration if audio_duration > 0 else 0.0

    print(f"Audio Duration: {audio_duration:.2f}s")
    print(f"Inference Duration: {inference_duration:.2f}s")
    print(f"Real-Time Factor (RTF): {rtf:.3f}x (lower is faster; < 1.0 is faster than real time)")
    print(f"Speedup Factor: {1.0 / rtf:.2f}x real-time")
    print(f"Detected Language: {result['language']} (p={result['language_probability']:.3f})")
    print(f"Transcribed Words Count: {result['word_count']}")
    print(f"Raw Text: {result['raw_text']}")

    print("\n--- 4. Word-Level Timestamps Sample ---")
    for i, w in enumerate(result["words"][:12]):
        print(f"  #{w['index']:02d} [{w['start']:5.2f}s -> {w['end']:5.2f}s] {w['word']:<15} (conf: {w['probability']:.2f})")
    if len(result["words"]) > 12:
        print(f"  ... and {len(result['words']) - 12} more words.")

    benchmark_summary = {
        "model": "tiny",
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": 4,
        "model_cache_size_mb": round(model_size_mb, 2),
        "audio_duration_seconds": audio_duration,
        "inference_duration_seconds": round(inference_duration, 3),
        "real_time_factor": round(rtf, 3),
        "speedup_factor": round(1.0 / rtf, 2) if rtf > 0 else 0,
        "words_transcribed": result["word_count"],
        "language": result["language"],
        "language_probability": result["language_probability"],
        "raw_text": result["raw_text"],
        "free_disk_space_after_gb": round(free_after_download / (1024**3), 2),
    }

    with open("fixtures/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(benchmark_summary, f, indent=2)
    print("\nBenchmark results saved to fixtures/benchmark_results.json")


if __name__ == "__main__":
    run_benchmark()
