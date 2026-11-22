"""Integration tests for Project Transcription API routes.

Directly tests route handlers to ensure deterministic execution on Windows 11.
"""

from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi import HTTPException

from clipforge.api.routes.transcription import (
    get_project_transcript,
    get_transcription_status,
    start_transcription,
)
from clipforge.core.config import settings
from clipforge.db.session import get_db_connection, init_db


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path: Path, monkeypatch):
    """Isolate storage and database paths for each test."""
    test_data_dir = tmp_path / "test_data"
    test_db_path = test_data_dir / "test_clipforge.db"

    monkeypatch.setattr(settings, "data_dir", test_data_dir)
    monkeypatch.setattr(settings, "db_name", "test_clipforge.db")
    settings.ensure_directories()
    init_db(test_db_path)


def test_start_transcription_not_found():
    """Verify 404 is raised when project does not exist."""
    with pytest.raises(HTTPException) as exc_info:
        start_transcription("non_existent_id")
    assert exc_info.value.status_code == 404


def test_start_transcription_no_audio():
    """Verify 400 is raised when project has no audio or audio has not been extracted."""
    project_id = "proj_no_audio"
    project_dir = settings.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, duration_seconds, width, height,
                                  fps, video_codec, audio_codec, has_audio, file_size_bytes,
                                  container_format, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "No Audio Video",
                str(project_dir / "silent.mp4"),
                10.0,
                1920,
                1080,
                30.0,
                "h264",
                "",
                0,
                2048,
                "mp4",
                "INGESTED",
            ),
        )
        conn.commit()

    with pytest.raises(HTTPException) as exc_info:
        start_transcription(project_id)
    assert exc_info.value.status_code == 400
    assert "no audio stream" in exc_info.value.detail.lower()


def test_start_transcription_duplicate_conflict():
    """Verify 409 Conflict is raised when transcription is already running."""
    project_id = "proj_running"
    project_dir = settings.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    audio_path = project_dir / "audio_16k.wav"
    audio_path.write_bytes(b"RIFF" + b"\x00" * 40)

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, duration_seconds, width, height,
                                  fps, video_codec, audio_codec, has_audio, file_size_bytes,
                                  container_format, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "Running Project",
                str(project_dir / "video.mp4"),
                15.0,
                1920,
                1080,
                30.0,
                "h264",
                "aac",
                1,
                4096,
                "mp4",
                "TRANSCRIBING",
            ),
        )
        conn.commit()

    with patch("clipforge.api.routes.transcription._active_jobs", {project_id: {"status": "IN_PROGRESS"}}):
        with pytest.raises(HTTPException) as exc_info:
            start_transcription(project_id)
        assert exc_info.value.status_code == 409
        assert "already in progress" in exc_info.value.detail.lower()


def test_start_transcription_success():
    """Verify 202 Accepted triggers background transcription worker."""
    project_id = "proj_success"
    project_dir = settings.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    audio_path = project_dir / "audio_16k.wav"
    audio_path.write_bytes(b"RIFF" + b"\x00" * 40)

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, duration_seconds, width, height,
                                  fps, video_codec, audio_codec, has_audio, file_size_bytes,
                                  container_format, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "Success Project",
                str(project_dir / "video.mp4"),
                15.0,
                1920,
                1080,
                30.0,
                "h264",
                "aac",
                1,
                4096,
                "mp4",
                "AUDIO_READY",
            ),
        )
        conn.commit()

    with patch("clipforge.api.routes.transcription.threading.Thread") as mock_thread:
        mock_instance = mock_thread.return_value
        response = start_transcription(project_id)

        assert response.project_id == project_id
        assert response.status == "ACCEPTED"
        assert response.model == "tiny"
        assert mock_instance.start.called

        # Project status in DB should be TRANSCRIBING
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT status FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            assert row["status"] == "TRANSCRIBING"


def test_get_transcription_status_endpoint():
    """Verify querying transcription status endpoint."""
    project_id = "proj_status_test"
    project_dir = settings.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, duration_seconds, width, height,
                                  fps, video_codec, audio_codec, has_audio, file_size_bytes,
                                  container_format, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "Status Test Project",
                str(project_dir / "video.mp4"),
                15.0,
                1920,
                1080,
                30.0,
                "h264",
                "aac",
                1,
                4096,
                "mp4",
                "TRANSCRIBED",
            ),
        )
        conn.commit()

    status_resp = get_transcription_status(project_id)
    assert status_resp.project_id == project_id
    assert status_resp.status == "COMPLETED"
    assert status_resp.progress_percent == 100


def test_get_project_transcript_not_found():
    """Verify 404 is returned when transcript is not found or not yet generated."""
    project_id = "proj_no_transcript"
    project_dir = settings.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, duration_seconds, width, height,
                                  fps, video_codec, audio_codec, has_audio, file_size_bytes,
                                  container_format, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "Empty Transcript Project",
                str(project_dir / "video.mp4"),
                10.0,
                1920,
                1080,
                30.0,
                "h264",
                "aac",
                1,
                2048,
                "mp4",
                "INGESTED",
            ),
        )
        conn.commit()

    with pytest.raises(HTTPException) as exc_info:
        get_project_transcript(project_id)
    assert exc_info.value.status_code == 404


def test_retry_failed_project_success():
    """Verify projects in FAILED status can be cleanly retried via API."""
    project_id = "proj_failed_retry"
    project_dir = settings.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    audio_path = project_dir / "audio_16k.wav"
    audio_path.write_bytes(b"RIFF" + b"\x00" * 40)

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, duration_seconds, width, height,
                                  fps, video_codec, audio_codec, has_audio, file_size_bytes,
                                  container_format, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "Failed Project to Retry",
                str(project_dir / "video.mp4"),
                12.0,
                1920,
                1080,
                30.0,
                "h264",
                "aac",
                1,
                2048,
                "mp4",
                "FAILED",
            ),
        )
        conn.commit()

    with patch("clipforge.api.routes.transcription.threading.Thread") as mock_thread:
        mock_instance = mock_thread.return_value
        response = start_transcription(project_id)

        assert response.project_id == project_id
        assert response.status == "ACCEPTED"
        assert response.model == "tiny"
        assert mock_instance.start.called

        # Status in DB should now be TRANSCRIBING
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT status FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            assert row["status"] == "TRANSCRIBING"


def test_get_failed_transcription_status_reports_error():
    """Verify get_transcription_status reports FAILED status and error message."""
    project_id = "proj_failed_status"
    project_dir = settings.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, duration_seconds, width, height,
                                  fps, video_codec, audio_codec, has_audio, file_size_bytes,
                                  container_format, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "Failed Status Project",
                str(project_dir / "video.mp4"),
                10.0,
                1920,
                1080,
                30.0,
                "h264",
                "aac",
                1,
                2048,
                "mp4",
                "FAILED",
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (id, project_id, stage, status, error_message, started_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """,
            ("job_fail_1", project_id, "TRANSCRIPTION", "FAILED", "Transcription was interrupted by server restart"),
        )
        conn.commit()

    status_resp = get_transcription_status(project_id)
    assert status_resp.project_id == project_id
    assert status_resp.status == "FAILED"
    assert status_resp.phase == "FAILED"
    assert status_resp.progress_percent == 0
    assert not status_resp.is_running
    assert status_resp.error == "Transcription was interrupted by server restart"


def test_get_transcription_status_active_job_telemetry():
    """Verify get_transcription_status provides phase, is_running, and timing telemetry."""
    project_id = "proj_telemetry_test"
    project_dir = settings.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, duration_seconds, width, height,
                                  fps, video_codec, audio_codec, has_audio, file_size_bytes,
                                  container_format, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "Telemetry Project",
                str(project_dir / "video.mp4"),
                14.0,
                1920,
                1080,
                30.0,
                "h264",
                "aac",
                1,
                2048,
                "mp4",
                "TRANSCRIBING",
            ),
        )
        conn.commit()

    active_mock = {
        project_id: {
            "status": "IN_PROGRESS",
            "phase": "TRANSCRIBING",
            "progress_percent": 70,
            "model_cached": True,
            "model_load_duration": 0.0,
            "inference_duration": None,
            "total_duration": None,
            "word_count": 0,
            "language": None,
            "language_probability": None,
            "error": None,
        }
    }

    with patch("clipforge.api.routes.transcription._active_jobs", active_mock):
        resp = get_transcription_status(project_id)
        assert resp.project_id == project_id
        assert resp.status == "IN_PROGRESS"
        assert resp.phase == "TRANSCRIBING"
        assert resp.model_cached is True
        assert resp.is_running is True
        assert resp.progress_percent == 70
        assert resp.model_load_duration == 0.0


def test_real_14s_sample_transcription_if_present():
    """Verify real 14s video audio completes transcription with accurate word timestamps."""
    real_audio_path = Path("clipforge-data/projects/648ef589-6314-4747-909b-a23d9295070a/audio_16k.wav")
    if not real_audio_path.exists():
        pytest.skip("Real 14s audio file not present in local workspace.")

    from clipforge.media.transcribe import transcription_engine

    result = transcription_engine.transcribe_file(real_audio_path)
    assert result["word_count"] > 20
    assert result["language"] == "en"
    assert result["duration"] > 10.0
    assert result["inference_duration"] < 10.0  # Must be faster than 10 seconds on this machine
    assert len(result["words"]) == result["word_count"]
    # Check word timestamps
    assert result["words"][0]["start"] >= 0.0
    assert result["words"][-1]["end"] <= 15.0

