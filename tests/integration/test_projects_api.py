"""Integration tests for Project Video Ingestion API routes.

Tests route endpoints directly to ensure reliable, high-speed execution
on Windows without Anyio background thread deadlocks.
"""

import io
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi import HTTPException, UploadFile

from clipforge.api.routes.projects import (
    delete_project,
    extract_project_audio,
    get_project,
    list_projects,
    stream_project_video,
    upload_video,
)
from clipforge.core.config import settings
from clipforge.db.session import init_db


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path: Path, monkeypatch):
    """Isolate storage and database paths for each test."""
    test_data_dir = tmp_path / "test_data"
    test_db_path = test_data_dir / "test_clipforge.db"

    monkeypatch.setattr(settings, "data_dir", test_data_dir)
    monkeypatch.setattr(settings, "db_name", "test_clipforge.db")
    settings.ensure_directories()
    init_db(test_db_path)


def test_upload_valid_video():
    """Verify successful upload of a valid video file creates project and extracts metadata."""
    valid_header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 1024

    mock_meta = {
        "duration_seconds": 60.0,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "video_codec": "h264",
        "audio_codec": "aac",
        "has_audio": True,
        "file_size_bytes": len(valid_header),
        "container_format": "mov,mp4,m4a",
    }

    with patch("clipforge.api.routes.projects.ffmpeg_engine.is_ffprobe_available", return_value=True), \
         patch("clipforge.api.routes.projects.ffmpeg_engine.probe_metadata", return_value=mock_meta):

        upload_file = UploadFile(filename="my_podcast.mp4", file=io.BytesIO(valid_header))
        project = upload_video(file=upload_file)

        assert project.id
        assert project.title == "My Podcast"
        assert project.duration_seconds == 60.0
        assert project.width == 1920
        assert project.height == 1080
        assert project.video_codec == "h264"
        assert project.has_audio is True
        assert project.status == "INGESTED"


def test_upload_invalid_extension():
    """Verify upload fails with 400 when file extension is not supported."""
    upload_file = UploadFile(filename="document.txt", file=io.BytesIO(b"Hello world"))
    with pytest.raises(HTTPException) as exc_info:
        upload_video(file=upload_file)
    assert exc_info.value.status_code == 400
    assert "Unsupported format" in exc_info.value.detail


def test_upload_invalid_magic_bytes():
    """Verify upload fails with 400 when file header signature is not a valid container."""
    fake_content = b"This is just raw text disguised with an mp4 extension."
    upload_file = UploadFile(filename="fake_video.mp4", file=io.BytesIO(fake_content))
    with pytest.raises(HTTPException) as exc_info:
        upload_video(file=upload_file)
    assert exc_info.value.status_code == 400
    assert "header signature does not match" in exc_info.value.detail


def test_upload_oversized_file(monkeypatch):
    """Verify upload aborts and returns 413 when file exceeds maximum configured size."""
    # Set limit to 200 bytes for testing
    monkeypatch.setattr(settings, "max_upload_size_bytes", 200)

    # Valid header but 500 bytes
    payload = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + (b"A" * 500)
    upload_file = UploadFile(filename="large_video.mp4", file=io.BytesIO(payload))

    with pytest.raises(HTTPException) as exc_info:
        upload_video(file=upload_file)
    assert exc_info.value.status_code == 413
    assert "exceeds maximum configured upload limit" in exc_info.value.detail


def test_duplicate_filename_isolation():
    """Verify uploading two files with the same name generates distinct projects without collisions."""
    valid_header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 128

    with patch("clipforge.api.routes.projects.ffmpeg_engine.is_ffprobe_available", return_value=False):
        u1 = UploadFile(filename="interview.mp4", file=io.BytesIO(valid_header))
        u2 = UploadFile(filename="interview.mp4", file=io.BytesIO(valid_header))

        p1 = upload_video(file=u1)
        p2 = upload_video(file=u2)

        assert p1.id != p2.id
        assert p1.source_file_path != p2.source_file_path
        assert Path(p1.source_file_path).exists()
        assert Path(p2.source_file_path).exists()


def test_list_and_get_project():
    """Verify listing projects and fetching a single project by ID."""
    valid_header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 128

    with patch("clipforge.api.routes.projects.ffmpeg_engine.is_ffprobe_available", return_value=False):
        u = UploadFile(filename="demo.mp4", file=io.BytesIO(valid_header))
        p = upload_video(file=u)

        # List projects
        projects = list_projects()
        assert len(projects) == 1
        assert projects[0].id == p.id

        # Get single project
        fetched = get_project(project_id=p.id)
        assert fetched.id == p.id

        # Non-existent project
        with pytest.raises(HTTPException) as exc_info:
            get_project(project_id="non_existent_id")
        assert exc_info.value.status_code == 404


def test_video_streaming_and_range_requests():
    """Verify HTTP range requests for in-browser video playback."""
    content = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + (b"0123456789" * 10)

    with patch("clipforge.api.routes.projects.ffmpeg_engine.is_ffprobe_available", return_value=False):
        u = UploadFile(filename="streamable.mp4", file=io.BytesIO(content))
        p = upload_video(file=u)

        # Full file streaming (200 OK)
        full_res = stream_project_video(project_id=p.id, range=None)
        assert full_res.status_code == 200
        assert full_res.headers["Content-Type"] == "video/mp4"

        # Partial content (206 Partial Content)
        range_res = stream_project_video(project_id=p.id, range="bytes=0-23")
        assert range_res.status_code == 206
        assert range_res.headers["Content-Range"].startswith("bytes 0-23/")

        # Invalid range (416 Unsatisfiable)
        with pytest.raises(HTTPException) as exc_info:
            stream_project_video(project_id=p.id, range="bytes=99999-999999")
        assert exc_info.value.status_code == 416


def test_delete_project():
    """Verify deleting a project removes database record and disk directory."""
    valid_header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 128

    with patch("clipforge.api.routes.projects.ffmpeg_engine.is_ffprobe_available", return_value=False):
        u = UploadFile(filename="to_delete.mp4", file=io.BytesIO(valid_header))
        p = upload_video(file=u)
        project_file = Path(p.source_file_path)
        assert project_file.exists()

        # Delete project
        del_res = delete_project(project_id=p.id)
        assert del_res["deleted"] is True

        # Confirm file removed from disk
        assert not project_file.exists()

        # Confirm 404 from API
        with pytest.raises(HTTPException) as exc_info:
            get_project(project_id=p.id)
        assert exc_info.value.status_code == 404


def test_extract_audio_endpoint():
    """Verify extract-audio endpoint triggers FFmpeg extraction and updates status."""
    valid_header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 128

    with patch("clipforge.api.routes.projects.ffmpeg_engine.is_ffprobe_available", return_value=False):
        u = UploadFile(filename="talk.mp4", file=io.BytesIO(valid_header))
        p = upload_video(file=u)

    # 1. Missing FFmpeg binary -> 503
    with patch("clipforge.api.routes.projects.ffmpeg_engine.is_available", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            extract_project_audio(project_id=p.id)
        assert exc_info.value.status_code == 503
        assert "FFmpeg binary is not installed" in exc_info.value.detail

    # 2. Successful extraction -> 200 and AUDIO_READY
    def fake_extract(source_video_path, output_audio_path, **kwargs):
        output_audio_path.write_bytes(b"RIFF$WAVEfmt " + b"\x00" * 44)
        return output_audio_path

    with patch("clipforge.api.routes.projects.ffmpeg_engine.is_available", return_value=True), \
         patch("clipforge.api.routes.projects.ffmpeg_engine.extract_audio", side_effect=fake_extract):

        res_extract = extract_project_audio(project_id=p.id)
        assert res_extract["status"] == "AUDIO_READY"
        assert res_extract["sample_rate"] == 16000

        # Verify DB updated
        updated_proj = get_project(project_id=p.id)
        assert updated_proj.status == "AUDIO_READY"
