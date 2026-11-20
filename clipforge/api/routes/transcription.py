"""Speech-to-Text Transcription API Router.

Provides endpoints to trigger background transcription, monitor progress,
prevent duplicate concurrent jobs, and retrieve timestamped transcript models.
"""

import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from clipforge.core.config import settings
from clipforge.core.logging import logger
from clipforge.db.models import TranscriptModel, SegmentModel, WordModel
from clipforge.db.session import get_db_connection
from clipforge.media.transcribe import transcription_engine, TranscriptionError

router = APIRouter(prefix="/projects", tags=["transcription"])

# In-memory tracking of active background transcription jobs
_active_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


class TranscriptionStartResponse(BaseModel):
    status: str
    project_id: str
    model: str
    message: str


class TranscriptionStatusResponse(BaseModel):
    project_id: str
    status: str
    model: str
    progress_percent: int
    error: Optional[str] = None


def _background_transcription_worker(project_id: str, language: Optional[str] = None):
    """Worker function executed inside a detached background thread."""
    with _jobs_lock:
        _active_jobs[project_id] = {
            "status": "IN_PROGRESS",
            "progress_percent": 25,
            "error": None,
        }

    try:
        logger.info(f"[BackgroundWorker] Starting transcription for project {project_id}")
        with _jobs_lock:
            if project_id in _active_jobs:
                _active_jobs[project_id]["progress_percent"] = 50

        transcription_engine.transcribe_project(project_id, language=language)

        with _jobs_lock:
            _active_jobs[project_id] = {
                "status": "COMPLETED",
                "progress_percent": 100,
                "error": None,
            }
        logger.info(f"[BackgroundWorker] Finished transcription for project {project_id}")

    except Exception as e:
        logger.error(f"[BackgroundWorker] Transcription failed for {project_id}: {e}")
        with _jobs_lock:
            _active_jobs[project_id] = {
                "status": "FAILED",
                "progress_percent": 0,
                "error": str(e),
            }
        # Update project status in DB to FAILED
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE projects SET status = 'FAILED' WHERE id = ?;", (project_id,))
            conn.commit()


@router.post(
    "/{project_id}/transcribe",
    response_model=TranscriptionStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_transcription(project_id: str, language: Optional[str] = None):
    """Trigger background transcription for a project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?;", (project_id,))
        project_row = cursor.fetchone()
        if not project_row:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    if not bool(project_row["has_audio"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transcribe project: video has no audio stream.",
        )

    # Check for duplicate job
    with _jobs_lock:
        job = _active_jobs.get(project_id)
        if job and job.get("status") == "IN_PROGRESS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Transcription is already in progress for project '{project_id}'.",
            )

    # Mark status as TRANSCRIBING in database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE projects SET status = 'TRANSCRIBING' WHERE id = ?;", (project_id,))
        conn.commit()

    # Launch detached thread worker
    worker = threading.Thread(
        target=_background_transcription_worker,
        args=(project_id, language),
        daemon=True,
    )
    worker.start()

    return TranscriptionStartResponse(
        status="ACCEPTED",
        project_id=project_id,
        model=settings.model_size,
        message=f"Transcription initiated using faster-whisper ({settings.model_size} on CPU int8).",
    )


@router.get(
    "/{project_id}/transcription-status",
    response_model=TranscriptionStatusResponse,
)
def get_transcription_status(project_id: str):
    """Query current transcription progress or error state for a project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM projects WHERE id = ?;", (project_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
        db_status = row["status"]
        db_error = None
        if db_status == "FAILED":
            cursor.execute(
                "SELECT error_message FROM jobs WHERE project_id = ? ORDER BY started_at DESC LIMIT 1;",
                (project_id,),
            )
            job_row = cursor.fetchone()
            if job_row and job_row["error_message"]:
                db_error = job_row["error_message"]

    with _jobs_lock:
        job = _active_jobs.get(project_id)

    if job:
        return TranscriptionStatusResponse(
            project_id=project_id,
            status=job["status"],
            model=settings.model_size,
            progress_percent=job["progress_percent"],
            error=job["error"],
        )

    # If not in active memory, derive from persistent DB status
    if db_status == "TRANSCRIBED":
        return TranscriptionStatusResponse(
            project_id=project_id,
            status="COMPLETED",
            model=settings.model_size,
            progress_percent=100,
        )
    elif db_status == "TRANSCRIBING":
        return TranscriptionStatusResponse(
            project_id=project_id,
            status="IN_PROGRESS",
            model=settings.model_size,
            progress_percent=50,
        )
    elif db_status == "FAILED":
        return TranscriptionStatusResponse(
            project_id=project_id,
            status="FAILED",
            model=settings.model_size,
            progress_percent=0,
            error=db_error or "Transcription failed during execution.",
        )

    return TranscriptionStatusResponse(
        project_id=project_id,
        status=db_status,
        model=settings.model_size,
        progress_percent=0,
    )


@router.get(
    "/{project_id}/transcript",
    response_model=TranscriptModel,
)
def get_project_transcript(project_id: str):
    """Retrieve full structured transcript with segments and word-level timestamps."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transcripts WHERE project_id = ?;", (project_id,))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found for project '{project_id}'. The project may not have been transcribed yet.",
        )

    json_path = Path(row["words_json_path"]) if row["words_json_path"] else settings.projects_dir / project_id / "transcript.json"

    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            segments = [
                SegmentModel(
                    id=s["id"],
                    start=s["start"],
                    end=s["end"],
                    text=s["text"],
                    words=[
                        WordModel(
                            index=w["index"],
                            word=w["word"],
                            start=w["start"],
                            end=w["end"],
                            probability=w.get("probability", 0.0),
                        )
                        for w in s.get("words", [])
                    ],
                )
                for s in data.get("segments", [])
            ]

            words = [
                WordModel(
                    index=w["index"],
                    word=w["word"],
                    start=w["start"],
                    end=w["end"],
                    probability=w.get("probability", 0.0),
                )
                for w in data.get("words", [])
            ]

            return TranscriptModel(
                id=row["id"],
                project_id=project_id,
                language=row["language"] or data.get("language", "en"),
                language_probability=row["language_probability"] or data.get("language_probability", 0.0),
                model_name=row["model_name"] or data.get("model", "tiny"),
                raw_text=row["raw_text"] or data.get("raw_text", ""),
                words_json_path=str(json_path.resolve()),
                word_count=row["word_count"] or len(words),
                segments=segments,
                words=words,
                status=row["status"] or "COMPLETED",
            )
        except Exception as e:
            logger.error(f"Failed to read transcript.json for {project_id}: {e}")

    # Fallback to DB row if JSON artifact is missing
    return TranscriptModel(
        id=row["id"],
        project_id=project_id,
        language=row["language"] or "en",
        language_probability=row["language_probability"] or 0.0,
        model_name=row["model_name"] or "tiny",
        raw_text=row["raw_text"] or "",
        words_json_path=row["words_json_path"] or "",
        word_count=row["word_count"] or 0,
        segments=[],
        words=[],
        status=row["status"] or "COMPLETED",
    )

