"""Unit tests for SQLite database initialization, WAL mode, and session reconciliation."""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from clipforge.core.config import settings
from clipforge.db.session import init_db, get_db_connection, reconcile_interrupted_jobs


def test_sqlite_wal_initialization(tmp_path: Path):
    """Verify SQLite initializes tables and enables WAL mode."""
    test_db = tmp_path / "test_clipforge.db"
    init_db(test_db)

    assert test_db.exists()

    with get_db_connection(test_db) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"

        # Verify tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "projects" in tables
        assert "jobs" in tables
        assert "transcripts" in tables
        assert "clips" in tables
        assert "export_assets" in tables


def test_init_and_connection_with_none_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify init_db and get_db_connection gracefully fall back to settings.db_path when db_path is None."""
    monkeypatch.setattr(settings, "data_dir", tmp_path / "isolated_data")
    monkeypatch.setattr(settings, "db_name", "fallback_default.db")

    default_expected_path = settings.db_path

    # Call with explicit None
    init_db(None)
    assert default_expected_path.exists()

    # Call get_db_connection with explicit None and default (no arg)
    with get_db_connection(None) as conn1:
        assert conn1 is not None
        cursor1 = conn1.cursor()
        cursor1.execute("SELECT count(*) FROM projects;")
        assert cursor1.fetchone()[0] == 0

    with get_db_connection() as conn2:
        assert conn2 is not None
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT count(*) FROM projects;")
        assert cursor2.fetchone()[0] == 0


def test_reconcile_interrupted_jobs_timezone_aware_timestamps(tmp_path: Path):
    """Verify reconcile_interrupted_jobs updates stale jobs with timezone-aware ISO timestamps."""
    test_db = tmp_path / "test_reconcile.db"
    init_db(test_db)

    with get_db_connection(test_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO projects (id, title, source_file_path, status)
            VALUES ('proj_stale_tx', 'Stale Transcription', 'dummy.mp4', 'TRANSCRIBING');
            """
        )
        cursor.execute(
            """
            INSERT INTO jobs (id, project_id, stage, status)
            VALUES ('job_tx_1', 'proj_stale_tx', 'TRANSCRIPTION', 'RUNNING');
            """
        )
        cursor.execute(
            """
            INSERT INTO projects (id, title, source_file_path, status)
            VALUES ('proj_stale_hl', 'Stale Highlights', 'dummy.mp4', 'DISCOVERING_HIGHLIGHTS');
            """
        )
        cursor.execute(
            """
            INSERT INTO jobs (id, project_id, stage, status)
            VALUES ('job_hl_1', 'proj_stale_hl', 'HIGHLIGHTS', 'RUNNING');
            """
        )
        conn.commit()

    # Reconcile using explicit Path
    count = reconcile_interrupted_jobs(test_db)
    assert count == 2

    with get_db_connection(test_db) as conn:
        cursor = conn.cursor()

        # Check project updated_at format
        cursor.execute("SELECT id, status, updated_at FROM projects ORDER BY id;")
        rows = cursor.fetchall()
        assert len(rows) == 2

        for row in rows:
            iso_str = row["updated_at"]
            assert iso_str is not None
            # Parse timestamp and verify timezone offset (+00:00)
            parsed_dt = datetime.fromisoformat(iso_str)
            assert parsed_dt.tzinfo is not None
            assert parsed_dt.utcoffset() == timezone.utc.utcoffset(None)

        # Check job finished_at format
        cursor.execute("SELECT id, status, error_message, finished_at FROM jobs ORDER BY id;")
        job_rows = cursor.fetchall()
        for j_row in job_rows:
            assert j_row["status"] == "FAILED"
            finished_str = j_row["finished_at"]
            assert finished_str is not None
            parsed_job_dt = datetime.fromisoformat(finished_str)
            assert parsed_job_dt.tzinfo is not None
            assert parsed_job_dt.utcoffset() == timezone.utc.utcoffset(None)
