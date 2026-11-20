"""Unit tests for video ingestion, header validation, filename sanitization, and FFmpeg/FFprobe operations."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from clipforge.api.routes.projects import sanitize_filename
from clipforge.media.ffmpeg import (
    EBML_HEADER,
    FFmpegError,
    FFmpegInterface,
    FFmpegNotFoundError,
    InvalidMediaFileError,
    NoAudioStreamError,
    is_valid_media_header,
)


def test_sanitize_filename():
    """Verify filename sanitization prevents directory traversal and cleans invalid characters."""
    assert sanitize_filename("my_video.mp4") == "my_video.mp4"
    assert sanitize_filename("../../etc/passwd.mp4") == "passwd.mp4"
    assert sanitize_filename("..\\..\\malicious\\payload.mov") == "payload.mov"
    assert sanitize_filename("spaced video (1) [2026].mkv") == "spaced_video__1___2026_.mkv"
    assert sanitize_filename("...hidden...mp4") == "hidden.mp4"


def test_is_valid_media_header():
    """Verify magic byte header detection for MP4/MOV and MKV/WebM."""
    # MP4 valid header: 4-byte size + 'ftyp'
    valid_mp4_header = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00"
    assert is_valid_media_header(valid_mp4_header, ".mp4") is True
    assert is_valid_media_header(valid_mp4_header, ".mov") is True

    # Matroska / WebM valid header: EBML signature
    valid_mkv_header = EBML_HEADER + b"\x42\x86\x81\x01\x42\xf7\x81\x01"
    assert is_valid_media_header(valid_mkv_header, ".mkv") is True
    assert is_valid_media_header(valid_mkv_header, ".webm") is True

    # Corrupt / invalid headers
    assert is_valid_media_header(b"GIF89a12345678", ".mp4") is False
    assert is_valid_media_header(b"\x89PNG\r\n\x1a\n123456", ".mov") is False
    assert is_valid_media_header(b"Short", ".mkv") is False
    assert is_valid_media_header(b"", ".webm") is False


def test_validate_video_file(tmp_path: Path):
    """Verify validate_video_file checks extension, existence, and magic bytes."""
    interface = FFmpegInterface()

    # 1. Non-existent file
    with pytest.raises(FileNotFoundError):
        interface.validate_video_file(tmp_path / "missing.mp4")

    # 2. Unsupported extension
    avi_file = tmp_path / "test.avi"
    avi_file.write_bytes(b"RIFF1234AVI ")
    with pytest.raises(InvalidMediaFileError, match="Unsupported file format"):
        interface.validate_video_file(avi_file)

    # 3. Empty file (0 bytes)
    empty_mp4 = tmp_path / "empty.mp4"
    empty_mp4.write_bytes(b"")
    with pytest.raises(InvalidMediaFileError, match="empty"):
        interface.validate_video_file(empty_mp4)

    # 4. Invalid header content
    fake_mp4 = tmp_path / "fake.mp4"
    fake_mp4.write_bytes(b"This is just a text file renamed to mp4.")
    with pytest.raises(InvalidMediaFileError, match="header signature does not match"):
        interface.validate_video_file(fake_mp4)

    # 5. Valid synthetic MP4 header
    valid_mp4 = tmp_path / "valid.mp4"
    valid_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
    # Should not raise
    interface.validate_video_file(valid_mp4)


def test_probe_metadata_mocked(tmp_path: Path):
    """Verify probe_metadata parses FFprobe JSON output accurately."""
    valid_mp4 = tmp_path / "sample.mp4"
    valid_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")

    mock_ffprobe = tmp_path / "ffprobe.exe"
    mock_ffprobe.write_text("dummy")

    mock_ffprobe_json = {
        "format": {
            "duration": "45.50",
            "size": "10485760",
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        },
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "30/1",
                "duration": "45.50",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
            },
        ],
    }

    interface = FFmpegInterface(custom_ffprobe_path=str(mock_ffprobe))

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(mock_ffprobe_json)
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        meta = interface.probe_metadata(valid_mp4)
        assert meta["duration_seconds"] == 45.5
        assert meta["width"] == 1920
        assert meta["height"] == 1080
        assert meta["fps"] == 30.0
        assert meta["video_codec"] == "h264"
        assert meta["audio_codec"] == "aac"
        assert meta["has_audio"] is True
        assert meta["file_size_bytes"] == 10485760


def test_probe_metadata_no_audio(tmp_path: Path):
    """Verify probe_metadata flags has_audio=False when no audio stream exists."""
    valid_mp4 = tmp_path / "silent.mp4"
    valid_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")

    mock_ffprobe = tmp_path / "ffprobe.exe"
    mock_ffprobe.write_text("dummy")

    mock_ffprobe_json = {
        "format": {"duration": "10.0", "size": "500000", "format_name": "mp4"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1280,
                "height": 720,
                "r_frame_rate": "24/1",
            }
        ],
    }

    interface = FFmpegInterface(custom_ffprobe_path=str(mock_ffprobe))

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps(mock_ffprobe_json)
        mock_run.return_value = mock_proc

        meta = interface.probe_metadata(valid_mp4)
        assert meta["has_audio"] is False
        assert meta["audio_codec"] == ""


def test_extract_audio_mocked_success(tmp_path: Path):
    """Verify extract_audio generates expected CLI args and outputs WAV."""
    source_mp4 = tmp_path / "input.mp4"
    source_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
    output_wav = tmp_path / "audio_16k.wav"

    mock_ffmpeg = tmp_path / "ffmpeg.exe"
    mock_ffmpeg.write_text("dummy")

    interface = FFmpegInterface(custom_ffmpeg_path=str(mock_ffmpeg))

    with patch("subprocess.run") as mock_run:
        def fake_run(cmd, **kwargs):
            # Simulate ffmpeg creating the output wav
            output_wav.write_bytes(b"RIFF$WAVEfmt " + b"\x00" * 44)
            proc = MagicMock()
            proc.returncode = 0
            proc.stderr = ""
            return proc

        mock_run.side_effect = fake_run

        result = interface.extract_audio(source_mp4, output_wav)
        assert result == output_wav
        assert output_wav.exists()

        # Check call arguments
        args = mock_run.call_args[0][0]
        assert "ffmpeg.exe" in args[0]
        assert "-vn" in args
        assert "-acodec" in args and "pcm_s16le" in args
        assert "-ar" in args and "16000" in args
        assert "-ac" in args and "1" in args


def test_extract_audio_no_audio_stream(tmp_path: Path):
    """Verify extract_audio raises NoAudioStreamError when video lacks audio."""
    source_mp4 = tmp_path / "no_audio.mp4"
    source_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
    output_wav = tmp_path / "out.wav"

    mock_ffmpeg = tmp_path / "ffmpeg.exe"
    mock_ffmpeg.write_text("dummy")

    interface = FFmpegInterface(custom_ffmpeg_path=str(mock_ffmpeg))

    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "Output file does not contain any stream"
        mock_run.return_value = mock_proc

        with pytest.raises(NoAudioStreamError):
            interface.extract_audio(source_mp4, output_wav)
