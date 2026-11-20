"""Unit tests for FFmpeg interface and error handling."""

from pathlib import Path
import pytest
from clipforge.media.ffmpeg import FFmpegInterface


def test_ffmpeg_interface_inspection():
    """Verify that FFmpeg interface detects binary presence or returns safe defaults."""
    interface = FFmpegInterface()
    info = interface.get_version_info()
    assert "ffmpeg" in info
    assert "ffprobe" in info


def test_probe_missing_file():
    """Verify error when attempting to probe a non-existent file."""
    interface = FFmpegInterface()
    with pytest.raises(FileNotFoundError):
        interface.probe_video_interface(Path("non_existent_video_file.mp4"))

