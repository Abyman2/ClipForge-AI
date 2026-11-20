"""Unit tests for SQLite database initialization and WAL mode."""

from pathlib import Path
from clipforge.db.session import init_db, get_db_connection


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

