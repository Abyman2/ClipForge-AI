"""Integration tests for the AI Highlight Discovery API.

Directly tests route handlers to ensure deterministic execution on Windows 11.
"""

import json
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi import HTTPException

from clipforge.api.routes.highlights import (
    _active_jobs,
    _jobs_lock,
    start_highlight_discovery,
    get_highlight_status,
    get_project_highlights,
    get_single_highlight,
    update_highlight_candidate,
    ClipPatchRequest,
)
from clipforge.core.config import settings
from clipforge.db.models import ClipModel
from clipforge.db.session import init_db, get_db_connection, reconcile_interrupted_jobs


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path: Path, monkeypatch):
    """Isolate database and storage for each test."""
    test_data = tmp_path / "data"
    test_data.mkdir(parents=True, exist_ok=True)
    test_db = test_data / "test_highlights.db"

    monkeypatch.setattr(settings, "data_dir", test_data)
    monkeypatch.setattr(settings, "db_name", "test_highlights.db")
    settings.ensure_directories()
    init_db(test_db)

    with _jobs_lock:
        _active_jobs.clear()

    yield test_db


def create_mock_project(
    project_id: str,
    status: str = "TRANSCRIBED",
    duration: float = 60.0,
) -> None:
    """Helper to insert a test project and dummy transcript artifact."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO projects (
                id, title, source_file_path, duration_seconds,
                has_audio, status
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (project_id, f"Project {project_id}", "dummy.mp4", duration, 1, status),
        )
        conn.commit()

    # Create dummy transcript disk artifact
    project_work_dir = settings.data_dir / "projects" / project_id / "work"
    project_work_dir.mkdir(parents=True, exist_ok=True)
    words = []
    t = 0.0
    for i in range(120):
        words.append({
            "index": i,
            "word": f"word{i}." if (i + 1) % 10 == 0 else f"word{i}",
            "start": round(t, 2),
            "end": round(t + 0.35, 2),
            "probability": 0.99,
        })
        t += 0.45

    transcript_data = {
        "project_id": project_id,
        "language": "en",
        "duration": duration,
        "text": "Sample transcript text.",
        "words": words,
        "segments": [],
    }
    with open(project_work_dir / "transcript.json", "w", encoding="utf-8") as f:
        json.dump(transcript_data, f)


def test_start_highlight_discovery_not_found():
    """Returns 404 if project does not exist."""
    with pytest.raises(HTTPException) as exc_info:
        start_highlight_discovery("nonexistent_proj")
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_start_highlight_discovery_invalid_status():
    """Returns 400 if project has not been transcribed yet."""
    create_mock_project("proj_not_transcribed", status="CREATED")
    with pytest.raises(HTTPException) as exc_info:
        start_highlight_discovery("proj_not_transcribed")
    assert exc_info.value.status_code == 400
    assert "transcribed" in exc_info.value.detail.lower()


def test_start_highlight_discovery_duplicate_conflict():
    """Returns 409 if highlight discovery is already in progress."""
    create_mock_project("proj_conflict", status="TRANSCRIBED")
    with _jobs_lock:
        _active_jobs["proj_conflict"] = {
            "status": "IN_PROGRESS",
            "progress_percent": 50,
            "candidate_count": 0,
            "mode": "heuristic_offline",
            "error": None,
        }

    with pytest.raises(HTTPException) as exc_info:
        start_highlight_discovery("proj_conflict")
    assert exc_info.value.status_code == 409
    assert "already in progress" in exc_info.value.detail.lower()


def test_start_highlight_discovery_success():
    """Successfully initiates background highlight discovery."""
    create_mock_project("proj_success", status="TRANSCRIBED")

    with patch("clipforge.ai.engine.highlight_engine.discover_highlights_for_project") as mock_discover:
        mock_discover.return_value = [
            ClipModel(
                id="clip_123",
                project_id="proj_success",
                start_word_index=0,
                end_word_index=45,
                start_time=0.0,
                end_time=20.0,
                title="Top Highlight",
                hook="Did you know?",
                description="Key moment.",
                rationale="High retention.",
                category="insight",
                engagement_score=9.0,
                validation_status="VALID",
                validation_reason="OK",
                selected=False,
                status="DISCOVERED",
            )
        ]

        res = start_highlight_discovery("proj_success")
        assert res.status == "ACCEPTED"
        assert res.project_id == "proj_success"
        assert res.mode in ("llm", "heuristic_offline")


def test_get_highlight_status_and_results():
    """Verify highlight status endpoint and clip retrieval."""
    proj_id = "proj_status_test"
    create_mock_project(proj_id, status="TRANSCRIBED")

    # Initial status should be IDLE
    res_status = get_highlight_status(proj_id)
    assert res_status.status == "IDLE"

    # Insert a dummy clip in the DB
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO clips (
                id, project_id, start_word_index, end_word_index,
                start_time, end_time, title, hook, description,
                rationale, category, engagement_score, validation_status,
                validation_reason, selected, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "clip_test_1",
                proj_id,
                5,
                45,
                2.5,
                22.0,
                "Awesome Moment",
                "Look at this",
                "Description here",
                "Rationale",
                "insight",
                8.5,
                "VALID",
                "OK",
                0,
                "DISCOVERED",
            ),
        )
        cursor.execute("UPDATE projects SET status = 'HIGHLIGHTS_READY' WHERE id = ?;", (proj_id,))
        conn.commit()

    # Status should now report COMPLETED
    res_status2 = get_highlight_status(proj_id)
    assert res_status2.status == "COMPLETED"
    assert res_status2.candidate_count == 1

    # Fetch highlights list
    clips = get_project_highlights(proj_id)
    assert len(clips) == 1
    assert clips[0].id == "clip_test_1"
    assert clips[0].title == "Awesome Moment"
    assert clips[0].selected is False

    # Fetch single highlight
    single_clip = get_single_highlight(proj_id, "clip_test_1")
    assert single_clip.id == "clip_test_1"

    # Patch selection toggle
    patch_req = ClipPatchRequest(selected=True, title="Updated Title")
    patched_clip = update_highlight_candidate(proj_id, "clip_test_1", patch_req)
    assert patched_clip.selected is True
    assert patched_clip.title == "Updated Title"


def test_startup_reconciliation_recovers_highlight_discovery():
    """Startup reconciliation safely restores interrupted DISCOVERING_HIGHLIGHTS projects to TRANSCRIBED."""
    proj_id = "proj_interrupted_hl"
    create_mock_project(proj_id, status="DISCOVERING_HIGHLIGHTS")

    # Run reconciliation
    reconciled_count = reconcile_interrupted_jobs()
    assert reconciled_count >= 1

    # Project status should be restored to TRANSCRIBED so user can retry
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM projects WHERE id = ?;", (proj_id,))
        row = cursor.fetchone()
        assert row["status"] == "TRANSCRIBED"
