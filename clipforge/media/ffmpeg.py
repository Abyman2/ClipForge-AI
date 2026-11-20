"""FFmpeg & FFprobe Media Processing Subsystem.

Provides robust, secure, and validated subprocess interfaces for FFmpeg/FFprobe,
including container format inspection, word-level audio extraction,
stream validation, and process isolation.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from clipforge.core.config import settings
from clipforge.core.logging import logger


class FFmpegError(Exception):
    """Base exception for FFmpeg/FFprobe operations."""
    pass


class FFmpegNotFoundError(FFmpegError):
    """Raised when FFmpeg or FFprobe executable is not found."""
    pass


class InvalidMediaFileError(FFmpegError):
    """Raised when a file is not a supported or valid video media container."""
    pass


class NoAudioStreamError(FFmpegError):
    """Raised when audio extraction is attempted on a video without an audio track."""
    pass


# Supported video extensions for ClipForge AI MVP
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}

# Recognized container header signatures (magic bytes)
EBML_HEADER = b"\x1a\x45\xdf\xa3"  # Matroska / WebM


def is_valid_media_header(header_bytes: bytes, extension: str) -> bool:
    """Validate initial file bytes against expected container signatures."""
    if len(header_bytes) < 8:
        return False

    ext = extension.lower()
    if ext in {".mkv", ".webm"}:
        return header_bytes.startswith(EBML_HEADER)

    if ext in {".mp4", ".mov"}:
        # ISO Base Media File Format: usually size (4 bytes) + 'ftyp' (or 'moov', 'mdat', 'wide')
        tag = header_bytes[4:8]
        if tag in {b"ftyp", b"moov", b"mdat", b"wide", b"skip"}:
            return True
        # Some MP4s might have zero-size or start directly with ftyp/skip
        if b"ftyp" in header_bytes[:32]:
            return True
        return False

    return False


class FFmpegInterface:
    """Production-grade interface for FFmpeg and FFprobe media operations."""

    def __init__(
        self,
        custom_ffmpeg_path: Optional[str] = None,
        custom_ffprobe_path: Optional[str] = None,
    ):
        self.ffmpeg_path = self._resolve_binary("ffmpeg", custom_ffmpeg_path or settings.custom_ffmpeg_path)
        self.ffprobe_path = self._resolve_binary("ffprobe", custom_ffprobe_path or settings.custom_ffprobe_path)

    @staticmethod
    def _resolve_binary(binary_name: str, custom_path: Optional[str]) -> Optional[str]:
        """Locate executable via custom override, project tools directory, or system PATH."""
        exe_name = f"{binary_name}.exe" if os.name == "nt" else binary_name

        # 1. Direct custom path
        if custom_path:
            p = Path(custom_path)
            if p.is_file():
                return str(p.resolve())
            candidate = p / exe_name
            if candidate.is_file():
                return str(candidate.resolve())

        # 2. Local workspace portable tools directory (tools/ffmpeg/bin)
        workspace_tools = Path.cwd() / "tools" / "ffmpeg" / "bin" / exe_name
        if workspace_tools.is_file():
            return str(workspace_tools.resolve())

        # 3. System PATH
        which_path = shutil.which(binary_name)
        if which_path and os.path.isfile(which_path):
            return which_path

        return None

    def is_available(self) -> bool:
        """Check if FFmpeg executable is available."""
        return self.ffmpeg_path is not None and os.path.isfile(self.ffmpeg_path)

    def is_ffprobe_available(self) -> bool:
        """Check if FFprobe executable is available."""
        return self.ffprobe_path is not None and os.path.isfile(self.ffprobe_path)

    def get_version_info(self) -> Dict[str, str]:
        """Return version diagnostic for FFmpeg and FFprobe."""
        res: Dict[str, str] = {
            "ffmpeg": "Not Found",
            "ffprobe": "Not Found",
            "ffmpeg_path": self.ffmpeg_path or "None",
            "ffprobe_path": self.ffprobe_path or "None",
        }

        if self.is_available():
            try:
                proc = subprocess.run(
                    [self.ffmpeg_path, "-version"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5.0,
                )
                res["ffmpeg"] = proc.stdout.splitlines()[0] if proc.stdout else "Available"
            except Exception as e:
                res["ffmpeg"] = f"Error probing: {e}"

        if self.is_ffprobe_available():
            try:
                proc = subprocess.run(
                    [self.ffprobe_path, "-version"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5.0,
                )
                res["ffprobe"] = proc.stdout.splitlines()[0] if proc.stdout else "Available"
            except Exception as e:
                res["ffprobe"] = f"Error probing: {e}"

        return res

    def validate_video_file(self, file_path: Path) -> None:
        """Validate that file exists, has a permitted extension, and matches header magic bytes."""
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Media file not found: {file_path}")

        ext = file_path.suffix.lower()
        if ext not in SUPPORTED_VIDEO_EXTENSIONS:
            raise InvalidMediaFileError(
                f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(SUPPORTED_VIDEO_EXTENSIONS))}"
            )

        file_size = file_path.stat().st_size
        if file_size == 0:
            raise InvalidMediaFileError("Media file is empty (0 bytes).")

        try:
            with open(file_path, "rb") as f:
                header = f.read(64)
            if not is_valid_media_header(header, ext):
                raise InvalidMediaFileError(
                    f"File header signature does not match valid {ext} container specification."
                )
        except (IOError, OSError) as e:
            raise InvalidMediaFileError(f"Failed to inspect media file header: {e}")

    def probe_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Inspect video container metadata via FFprobe JSON output."""
        self.validate_video_file(file_path)

        if not self.is_ffprobe_available():
            raise FFmpegNotFoundError(
                "FFprobe is not available on this system. Cannot inspect video metadata."
            )

        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            "-show_error",
            str(file_path),
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=15.0,
            )
        except subprocess.TimeoutExpired:
            raise FFmpegError("FFprobe metadata inspection timed out after 15 seconds.")
        except Exception as e:
            raise FFmpegError(f"Failed to execute FFprobe subprocess: {e}")

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() if proc.stderr else f"Exit code {proc.returncode}"
            raise FFmpegError(f"FFprobe inspection failed: {err_msg}")

        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise FFmpegError(f"Failed to parse FFprobe JSON output: {e}")

        if "error" in data:
            raise FFmpegError(f"FFprobe returned error: {data['error'].get('string', 'Unknown error')}")

        streams: List[Dict[str, Any]] = data.get("streams", [])
        fmt: Dict[str, Any] = data.get("format", {})

        video_stream: Optional[Dict[str, Any]] = None
        audio_stream: Optional[Dict[str, Any]] = None

        for stream in streams:
            codec_type = stream.get("codec_type")
            if codec_type == "video" and video_stream is None:
                video_stream = stream
            elif codec_type == "audio" and audio_stream is None:
                audio_stream = stream

        if not video_stream:
            raise InvalidMediaFileError("No video stream found in the specified media file.")

        # Duration resolution (format level preferred, fallback to video stream)
        duration = 0.0
        if "duration" in fmt:
            try:
                duration = float(fmt["duration"])
            except (ValueError, TypeError):
                pass
        if duration <= 0.0 and "duration" in video_stream:
            try:
                duration = float(video_stream["duration"])
            except (ValueError, TypeError):
                pass

        # Dimensions
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))

        # Frame rate calculation (r_frame_rate or avg_frame_rate, e.g. '30/1' or '30000/1001')
        fps = 0.0
        fps_str = video_stream.get("r_frame_rate") or video_stream.get("avg_frame_rate", "0/0")
        if "/" in fps_str:
            num, den = fps_str.split("/", 1)
            try:
                den_f = float(den)
                if den_f > 0:
                    fps = round(float(num) / den_f, 2)
            except (ValueError, ZeroDivisionError):
                fps = 0.0

        # Codecs
        video_codec = str(video_stream.get("codec_name", ""))
        audio_codec = str(audio_stream.get("codec_name", "")) if audio_stream else ""
        has_audio = audio_stream is not None

        # File size
        file_size = int(fmt.get("size", file_path.stat().st_size))
        container_format = str(fmt.get("format_name", ""))

        return {
            "file_path": str(file_path.resolve()),
            "duration_seconds": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "video_codec": video_codec,
            "audio_codec": audio_codec,
            "has_audio": has_audio,
            "file_size_bytes": file_size,
            "container_format": container_format,
        }

    def probe_video_interface(self, file_path: Path) -> Dict[str, Any]:
        """Backwards-compatible alias for probe_metadata."""
        return self.probe_metadata(file_path)

    def extract_audio(
        self,
        source_video_path: Path,
        output_audio_path: Path,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> Path:
        """Extract standardized 16kHz 16-bit mono PCM WAV for Whisper transcription."""
        self.validate_video_file(source_video_path)

        if not self.is_available():
            raise FFmpegNotFoundError("FFmpeg is not available on this system. Cannot extract audio.")

        # Ensure output directory exists
        output_audio_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_path,
            "-y",  # overwrite output
            "-i", str(source_video_path),
            "-vn",  # disable video recording
            "-acodec", "pcm_s16le",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            str(output_audio_path),
        ]

        logger.info(f"Extracting audio: {source_video_path.name} -> {output_audio_path.name} ({sample_rate}Hz mono)")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=180.0,
            )
        except subprocess.TimeoutExpired:
            if output_audio_path.exists():
                output_audio_path.unlink(missing_ok=True)
            raise FFmpegError("FFmpeg audio extraction timed out after 180 seconds.")
        except Exception as e:
            if output_audio_path.exists():
                output_audio_path.unlink(missing_ok=True)
            raise FFmpegError(f"Failed to execute FFmpeg audio extraction: {e}")

        if proc.returncode != 0:
            stderr = proc.stderr.lower() if proc.stderr else ""
            if output_audio_path.exists():
                output_audio_path.unlink(missing_ok=True)

            if "does not contain any stream" in stderr or "matches no streams" in stderr or "output file is empty" in stderr:
                raise NoAudioStreamError("The video file does not contain an audio stream to extract.")

            raise FFmpegError(f"FFmpeg audio extraction failed (code {proc.returncode}): {proc.stderr.strip()}")

        if not output_audio_path.exists() or output_audio_path.stat().st_size == 0:
            raise FFmpegError("FFmpeg reported success but extracted audio file is missing or empty.")

        return output_audio_path


# Global singleton instance
ffmpeg_engine = FFmpegInterface()
