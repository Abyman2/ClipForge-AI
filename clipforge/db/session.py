"""SQLite Database Session & Connection Management.

Enforces Write-Ahead Logging (WAL mode) and synchronous=NORMAL
to allow non-blocking concurrent reads while background workers write progress.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional
from clipforge.core.config import settings
from clipforge.core.logging import logger

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_file_path TEXT NOT NULL,
    duration_seconds REAL DEFAULT 0.0,
    width INTEGER DEFAULT 0,
    height INTEGER DEFAULT 0,
    fps REAL DEFAULT 0.0,
    video_codec TEXT DEFAULT '',
    audio_codec TEXT DEFAULT '',
    has_audio INTEGER DEFAULT 1,
    file_size_bytes INTEGER DEFAULT 0,
    container_format TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'CREATED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    progress_percent INTEGER DEFAULT 0,
    log_output TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transcripts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    raw_text TEXT DEFAULT '',
    words_json_path TEXT DEFAULT '',
    language TEXT DEFAULT 'en',
    language_probability REAL DEFAULT 0.0,
    model_name TEXT DEFAULT 'tiny',
    word_count INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'COMPLETED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clips (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    start_word_index INTEGER NOT NULL,
    end_word_index INTEGER NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    title TEXT NOT NULL,
    hook TEXT DEFAULT '',
    description TEXT DEFAULT '',
    rationale TEXT DEFAULT '',
    engagement_score REAL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'DISCOVERED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS export_assets (
    id TEXT PRIMARY KEY,
    clip_id TEXT NOT NULL,
    output_path TEXT NOT NULL,
    file_size_bytes INTEGER DEFAULT 0,
    encoder_used TEXT DEFAULT 'libx264',
    render_duration_seconds REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(clip_id) REFERENCES clips(id) ON DELETE CASCADE
);
"""


def init_db(db_path: Path = None) -> None:
    """Initialize the SQLite database with WAL mode and create base schema."""
    target_path = db_path or settings.db_path
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target_path, timeout=30.0)
    try:
        cursor = conn.cursor()
        # Enable WAL mode for concurrency
        cursor.execute("PRAGMA journal_mode = WAL;")
        wal_result = cursor.fetchone()
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.executescript(SCHEMA_SQL)

        # Migrate existing columns for projects table if missing
        cursor.execute("PRAGMA table_info(projects);")
        existing_cols = {row[1] for row in cursor.fetchall()}
        column_defs = {
            "video_codec": "TEXT DEFAULT ''",
            "audio_codec": "TEXT DEFAULT ''",
            "has_audio": "INTEGER DEFAULT 1",
            "file_size_bytes": "INTEGER DEFAULT 0",
            "container_format": "TEXT DEFAULT ''",
        }
        for col_name, col_type in column_defs.items():
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type};")

        # Migrate existing columns for transcripts table if missing
        cursor.execute("PRAGMA table_info(transcripts);")
        existing_transcript_cols = {row[1] for row in cursor.fetchall()}
        transcript_column_defs = {
            "language_probability": "REAL DEFAULT 0.0",
            "model_name": "TEXT DEFAULT 'tiny'",
            "word_count": "INTEGER DEFAULT 0",
            "status": "TEXT DEFAULT 'COMPLETED'",
        }
        for col_name, col_type in transcript_column_defs.items():
            if col_name not in existing_transcript_cols:
                cursor.execute(f"ALTER TABLE transcripts ADD COLUMN {col_name} {col_type};")

        conn.commit()
        logger.info(f"Initialized database at {target_path} (Journal Mode: {wal_result[0] if wal_result else 'WAL'})")
    finally:
        conn.close()


@contextmanager
def get_db_connection(db_path: Path = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections with row_factory enabled."""
    target_path = db_path or settings.db_path
    conn = sqlite3.connect(target_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def reconcile_interrupted_jobs(db_path: Optional[Path] = None) -> int:
    """Reconcile stale in-progress jobs upon application startup.

    Any project left in TRANSCRIBING status from a previous process (e.g. server restart)
    is marked as FAILED with an explicit error record, enabling clean retry.
    Returns the count of reconciled projects.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM projects WHERE status = 'TRANSCRIBING';")
        stale_rows = cursor.fetchall()
        if not stale_rows:
            return 0

        stale_ids = [row["id"] for row in stale_rows]
        now_iso = datetime.utcnow().isoformat()
        cursor.execute(
            """
            UPDATE projects 
            SET status = 'FAILED', updated_at = ? 
            WHERE status = 'TRANSCRIBING';
            """,
            (now_iso,),
        )
        for proj_id in stale_ids:
            cursor.execute(
                """
                UPDATE transcripts 
                SET status = 'FAILED' 
                WHERE project_id = ? AND status != 'COMPLETED';
                """,
                (proj_id,),
            )
            cursor.execute(
                """
                UPDATE jobs 
                SET status = 'FAILED', 
                    error_message = 'Transcription was interrupted by server restart',
                    finished_at = ?
                WHERE project_id = ? AND status IN ('PENDING', 'RUNNING');
                """,
                (now_iso, proj_id),
            )
        conn.commit()
        logger.warning(
            f"Startup reconciliation: marked {len(stale_ids)} interrupted project(s) as FAILED: {stale_ids}"
        )
        return len(stale_ids)


