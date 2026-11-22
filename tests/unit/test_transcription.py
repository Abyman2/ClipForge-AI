"""Unit tests for TranscriptionEngine, word indexing, and transcript persistence."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from clipforge.core.config import settings
from clipforge.db.models import ProjectModel, TranscriptModel
from clipforge.db.session import get_db_connection, init_db, reconcile_interrupted_jobs
from clipforge.media.transcribe import (
    AudioCorruptedError,
    AudioFileNotFoundError,
    ModelLoadError,
    TranscriptionEngine,
    TranscriptionError,
)


class MockWord:
    def __init__(self, start: float, end: float, word: str, probability: float):
        self.start = start
        self.end = end
        self.word = word
        self.probability = probability


class MockSegment:
    def __init__(self, id: int, start: float, end: float, text: str, words: list):
        self.id = id
        self.start = start
        self.end = end
        self.text = text
        self.words = words


class MockInfo:
    language = "en"
    language_probability = 0.985
    duration = 8.5


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path: Path, monkeypatch):
    """Set up isolated project directories and database."""
    test_data_dir = tmp_path / "data"
    test_db_path = test_data_dir / "test.db"
    monkeypatch.setattr(settings, "data_dir", test_data_dir)
    monkeypatch.setattr(settings, "db_name", "test.db")
    settings.ensure_directories()
    init_db(test_db_path)


def test_transcription_engine_init():
    """Verify default engine configuration targets Intel CPU int8."""
    engine = TranscriptionEngine(model_size="tiny", device="cpu", compute_type="int8", cpu_threads=4)
    assert engine.model_size == "tiny"
    assert engine.device == "cpu"
    assert engine.compute_type == "int8"
    assert engine.cpu_threads == 4


def test_transcribe_audio_missing_file():
    """Verify AudioFileNotFoundError raised when input audio file is absent."""
    engine = TranscriptionEngine(model_size="tiny")
    with pytest.raises(AudioFileNotFoundError):
        engine.transcribe_audio(
            audio_path=Path("non_existent_audio.wav"),
            project_id="proj_missing",
        )


def test_transcribe_audio_success_and_indexing(tmp_path: Path):
    """Verify transcription parses segments, words, strictly sequential 0..N-1 indices, and persists."""
    project_id = "proj_test_123"
    project_dir = settings.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    # Insert initial project record
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
                "Test Project",
                str(project_dir / "video.mp4"),
                8.5,
                1920,
                1080,
                30.0,
                "h264",
                "aac",
                1,
                1024,
                "mp4",
                "AUDIO_READY",
            ),
        )
        conn.commit()

    audio_file = project_dir / "audio_16k.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

    # Mock faster_whisper segments and words
    mock_segments = [
        MockSegment(
            id=0,
            start=0.0,
            end=3.5,
            text=" Welcome to ClipForge AI.",
            words=[
                MockWord(0.0, 0.8, " Welcome", 0.99),
                MockWord(0.8, 1.2, " to", 0.98),
                MockWord(1.2, 2.5, " ClipForge", 0.95),
                MockWord(2.5, 3.5, " AI.", 0.97),
            ],
        ),
        MockSegment(
            id=1,
            start=3.6,
            end=6.0,
            text=" Local video clipping.",
            words=[
                MockWord(3.6, 4.2, " Local", 0.96),
                MockWord(4.2, 5.0, " video", 0.98),
                MockWord(5.0, 6.0, " clipping.", 0.99),
            ],
        ),
    ]
    mock_info = MockInfo()

    engine = TranscriptionEngine(model_size="tiny")

    mock_whisper_instance = MagicMock()
    mock_whisper_instance.transcribe.return_value = (mock_segments, mock_info)

    with patch.object(engine, "_load_model", return_value=mock_whisper_instance):
        result = engine.transcribe_audio(
            audio_path=audio_file,
            project_id=project_id,
            language="en",
        )

    # Verify returned TranscriptModel
    assert isinstance(result, TranscriptModel)
    assert result.project_id == project_id
    assert result.language == "en"
    assert result.language_probability == 0.985
    assert len(result.segments) == 2
    assert len(result.words) == 7

    # Verify contiguous word indexing 0..6
    for expected_idx, word in enumerate(result.words):
        assert word.index == expected_idx

    assert result.words[0].word == "Welcome"
    assert result.words[0].start == 0.0
    assert result.words[0].end == 0.8
    assert result.words[6].word == "clipping."

    # Verify disk artifact exists and matches
    artifact_path = project_dir / "transcript.json"
    assert artifact_path.exists()
    disk_data = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert disk_data["project_id"] == project_id
    assert len(disk_data["words"]) == 7
    assert disk_data["words"][3]["word"] == "AI."
    assert disk_data["words"][3]["index"] == 3

    # Verify database record updated
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT status FROM projects WHERE id = ?", (project_id,))
        proj_row = cursor.fetchone()
        assert proj_row["status"] == "TRANSCRIBED"

        cursor = conn.execute("SELECT * FROM transcripts WHERE project_id = ?", (project_id,))
        trans_row = cursor.fetchone()
        assert trans_row is not None
        assert trans_row["language"] == "en"
        assert trans_row["word_count"] == 7
        assert trans_row["status"] == "COMPLETED"


def test_get_transcript_and_status(tmp_path: Path):
    """Verify loading transcript from disk artifact and querying transcription status."""
    project_id = "proj_query_456"
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
                "Query Project",
                str(project_dir / "video.mp4"),
                5.0,
                1920,
                1080,
                30.0,
                "h264",
                "aac",
                1,
                1024,
                "mp4",
                "TRANSCRIBED",
            ),
        )
        conn.execute(
            """
            INSERT INTO transcripts (project_id, language, language_probability, model_name,
                                     raw_text, word_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, "en", 0.99, "tiny", "Hello world", 2, "COMPLETED"),
        )
        conn.commit()

    artifact_path = project_dir / "transcript.json"
    transcript_payload = {
        "project_id": project_id,
        "language": "en",
        "language_probability": 0.99,
        "duration": 5.0,
        "text": "Hello world",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 2.0,
                "text": "Hello world",
                "words": [
                    {"index": 0, "start": 0.0, "end": 0.9, "word": "Hello", "probability": 0.99},
                    {"index": 1, "start": 1.0, "end": 2.0, "word": "world", "probability": 0.98},
                ],
            }
        ],
        "words": [
            {"index": 0, "start": 0.0, "end": 0.9, "word": "Hello", "probability": 0.99},
            {"index": 1, "start": 1.0, "end": 2.0, "word": "world", "probability": 0.98},
        ],
    }
    artifact_path.write_text(json.dumps(transcript_payload), encoding="utf-8")

    engine = TranscriptionEngine(model_size="tiny")

    # Load transcript
    model = engine.get_transcript(project_id)
    assert model is not None
    assert model.project_id == project_id
    assert len(model.words) == 2
    assert model.words[0].word == "Hello"

    # Load status
    status = engine.get_transcription_status(project_id)
    assert status["status"] == "COMPLETED"
    assert status["word_count"] == 2
    assert status["language"] == "en"
    assert status["is_running"] is False


def test_atomic_write_success(tmp_path: Path):
    """Verify write_transcript_atomically produces a valid JSON artifact."""
    target_file = tmp_path / "project_1" / "transcript.json"
    payload = {"project_id": "proj_1", "text": "Atomic test", "words": [1, 2, 3]}

    TranscriptionEngine.write_transcript_atomically(target_file, payload)

    assert target_file.exists()
    assert not target_file.with_suffix(".tmp").exists()
    loaded = json.loads(target_file.read_text(encoding="utf-8"))
    assert loaded["project_id"] == "proj_1"
    assert loaded["text"] == "Atomic test"


def test_atomic_write_failure_preserves_original(tmp_path: Path):
    """Verify write failure does not corrupt existing transcript and cleans up temp files."""
    target_file = tmp_path / "project_2" / "transcript.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(json.dumps({"original": "safe_data"}), encoding="utf-8")

    # Simulate serialization error or disk failure during dump
    class UnserializableObject:
        pass

    bad_payload = {"unserializable": UnserializableObject()}

    with pytest.raises(TypeError):
        TranscriptionEngine.write_transcript_atomically(target_file, bad_payload)

    # Original file must be completely untouched
    assert target_file.exists()
    loaded = json.loads(target_file.read_text(encoding="utf-8"))
    assert loaded["original"] == "safe_data"

    # Temporary file must be cleaned up
    assert not target_file.with_suffix(".tmp").exists()


def test_startup_reconciliation_marks_transcribing_as_failed():
    """Verify startup reconciliation marks stale TRANSCRIBING projects as FAILED while preserving others."""
    with get_db_connection() as conn:
        # 1. Stale transcribing project
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, status)
            VALUES (?, ?, ?, ?);
            """,
            ("proj_stale_1", "Stale Project 1", "video.mp4", "TRANSCRIBING"),
        )
        conn.execute(
            """
            INSERT INTO jobs (id, project_id, stage, status)
            VALUES (?, ?, ?, ?);
            """,
            ("job_stale_1", "proj_stale_1", "TRANSCRIPTION", "RUNNING"),
        )
        # 2. Ingested project (should remain INGESTED)
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, status)
            VALUES (?, ?, ?, ?);
            """,
            ("proj_ingested", "Ingested Project", "video.mp4", "INGESTED"),
        )
        # 3. Audio ready project (should remain AUDIO_READY)
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, status)
            VALUES (?, ?, ?, ?);
            """,
            ("proj_audio_ready", "Audio Ready", "video.mp4", "AUDIO_READY"),
        )
        # 4. Transcribed project (should remain TRANSCRIBED)
        conn.execute(
            """
            INSERT INTO projects (id, title, source_file_path, status)
            VALUES (?, ?, ?, ?);
            """,
            ("proj_completed", "Completed", "video.mp4", "TRANSCRIBED"),
        )
        conn.commit()

    # Run reconciliation
    reconciled_count = reconcile_interrupted_jobs()
    assert reconciled_count == 1

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM projects ORDER BY id;")
        statuses = {row["id"]: row["status"] for row in cursor.fetchall()}

        assert statuses["proj_stale_1"] == "FAILED"
        assert statuses["proj_ingested"] == "INGESTED"
        assert statuses["proj_audio_ready"] == "AUDIO_READY"
        assert statuses["proj_completed"] == "TRANSCRIBED"

        # Check job error message
        cursor.execute("SELECT error_message FROM jobs WHERE project_id = ?;", ("proj_stale_1",))
        job_row = cursor.fetchone()
        assert job_row is not None
        assert "interrupted by server restart" in job_row["error_message"].lower()


def test_transcribe_audio_corrupted_file(tmp_path: Path):
    """Verify AudioCorruptedError is raised when audio file has fewer than 44 bytes."""
    engine = TranscriptionEngine(model_size="tiny")
    corrupt_audio = tmp_path / "corrupt.wav"
    corrupt_audio.write_bytes(b"RIFF_TOO_SHORT")  # 14 bytes (< 44)
    with pytest.raises(AudioCorruptedError) as exc_info:
        engine.transcribe_file(corrupt_audio)
    assert "corrupted" in str(exc_info.value).lower()


def test_model_caching_and_status():
    """Verify is_model_loaded reflects memory cache and get_model_status provides telemetry."""
    engine = TranscriptionEngine(model_size="tiny", cpu_threads=4)
    assert not engine.is_model_loaded

    status_before = engine.get_model_status()
    assert status_before["model_size"] == "tiny"
    assert status_before["cpu_threads"] == 4
    assert not status_before["is_loaded"]

    # Simulate model loading
    mock_model = MagicMock()
    with patch.object(engine, "_load_model", return_value=mock_model):
        engine._model = mock_model
        assert engine.is_model_loaded
        status_after = engine.get_model_status()
        assert status_after["is_loaded"]


def test_model_load_failure():
    """Verify ModelLoadError is raised when faster-whisper fails to initialize."""
    engine = TranscriptionEngine(model_size="non_existent_model_xyz")
    with patch("faster_whisper.WhisperModel", side_effect=RuntimeError("Out of memory")):
        with pytest.raises(ModelLoadError) as exc_info:
            engine._load_model()
        assert "failed to load whisper model" in str(exc_info.value).lower()


def test_transcription_engine_progress_callback(tmp_path: Path):
    """Verify on_progress callback receives LOADING_MODEL and TRANSCRIBING phases."""
    engine = TranscriptionEngine(model_size="tiny")
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MockInfo())

    phases_recorded = []

    def progress_tracker(phase, percent, extra):
        phases_recorded.append((phase, percent))

    with patch.object(engine, "get_model", return_value=mock_model):
        result = engine.transcribe_file(audio_file, on_progress=progress_tracker)

    assert ("LOADING_MODEL", 35) in phases_recorded
    assert ("TRANSCRIBING", 70) in phases_recorded
    assert "model_load_duration" in result
    assert "inference_duration" in result
    assert "total_duration" in result


def test_transcribe_project_creates_and_completes_job_record(tmp_path: Path):
    """Verify transcribe_project records execution in SQLite jobs table."""
    project_id = "proj_job_audit_test"
    project_dir = settings.get_project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    audio_file = project_dir / "audio_16k.wav"
    audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

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
                "Job Audit Project",
                str(project_dir / "video.mp4"),
                5.0,
                1920,
                1080,
                30.0,
                "h264",
                "aac",
                1,
                2048,
                "mp4",
                "AUDIO_READY",
            ),
        )
        conn.commit()

    engine = TranscriptionEngine(model_size="tiny")
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], MockInfo())

    with patch.object(engine, "get_model", return_value=mock_model):
        engine.transcribe_project(project_id)

    # Check jobs table
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE project_id = ? AND stage = 'TRANSCRIPTION';", (project_id,))
        job_row = cursor.fetchone()

        assert job_row is not None
        assert job_row["status"] == "COMPLETED"
        assert job_row["progress_percent"] == 100
        assert job_row["started_at"] is not None
        assert job_row["finished_at"] is not None
        assert "completed successfully" in job_row["log_output"].lower()

