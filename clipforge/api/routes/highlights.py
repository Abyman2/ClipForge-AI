"""AI Highlight Discovery API Router.

Provides endpoints to trigger highlight discovery, monitor job progress,
prevent duplicate concurrent jobs, retrieve candidate clips, and update candidate selections.
"""

import json
import threading
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from clipforge.ai.engine import highlight_engine
from clipforge.core.config import settings
from clipforge.core.logging import logger
from clipforge.db.models import ClipModel
from clipforge.db.session import get_db_connection

router = APIRouter(prefix="/projects", tags=["highlights"])

# In-memory tracking of active background discovery jobs
_active_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


class HighlightStartResponse(BaseModel):
    status: str
    project_id: str
    mode: str
    message: str


class HighlightStatusResponse(BaseModel):
    project_id: str
    status: str
    progress_percent: int
    candidate_count: int
    mode: str
    error: Optional[str] = None
    is_running: bool


class ClipPatchRequest(BaseModel):
    selected: Optional[bool] = None
    title: Optional[str] = None
    status: Optional[str] = None


def _background_highlight_worker(project_id: str, video_duration: Optional[float] = None):
    """Worker function executed inside a detached background thread."""
    mode = "llm" if highlight_engine.adapter.has_api_key else "heuristic_offline"
    with _jobs_lock:
        _active_jobs[project_id] = {
            "status": "IN_PROGRESS",
            "progress_percent": 25,
            "candidate_count": 0,
            "mode": mode,
            "error": None,
        }

    try:
        logger.info(f"[BackgroundHighlightWorker] Starting discovery for project {project_id} (mode={mode})")
        with _jobs_lock:
            if project_id in _active_jobs:
                _active_jobs[project_id]["progress_percent"] = 50

        # Mark project status in DB as DISCOVERING_HIGHLIGHTS
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE projects SET status = 'DISCOVERING_HIGHLIGHTS' WHERE id = ?;",
                (project_id,),
            )
            conn.commit()

        clips = highlight_engine.discover_highlights_for_project(
            project_id=project_id,
            video_duration=video_duration,
        )

        with _jobs_lock:
            _active_jobs[project_id] = {
                "status": "COMPLETED",
                "progress_percent": 100,
                "candidate_count": len(clips),
                "mode": mode,
                "error": None,
            }
        logger.info(
            f"[BackgroundHighlightWorker] Completed highlight discovery for {project_id}: {len(clips)} clips found."
        )

    except Exception as e:
        logger.error(f"[BackgroundHighlightWorker] Discovery failed for {project_id}: {e}")
        with _jobs_lock:
            _active_jobs[project_id] = {
                "status": "FAILED",
                "progress_percent": 0,
                "candidate_count": 0,
                "mode": mode,
                "error": str(e),
            }
        # Revert project status in DB to TRANSCRIBED (transcript is still valid)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE projects SET status = 'TRANSCRIBED' WHERE id = ?;",
                (project_id,),
            )
            conn.commit()


@router.post(
    "/{project_id}/highlights/discover",
    response_model=HighlightStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_highlight_discovery(project_id: str):
    """Trigger background highlight discovery for a transcribed project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?;", (project_id,))
        project_row = cursor.fetchone()
        if not project_row:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    proj_status = project_row["status"]
    if proj_status not in ("TRANSCRIBED", "HIGHLIGHTS_READY"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot discover highlights: project status is '{proj_status}'. "
                "Project must be in 'TRANSCRIBED' or 'HIGHLIGHTS_READY' status."
            ),
        )

    # Check for duplicate concurrent discovery jobs
    with _jobs_lock:
        job = _active_jobs.get(project_id)
        if job and job.get("status") == "IN_PROGRESS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Highlight discovery for project '{project_id}' is already in progress.",
            )

    video_duration = float(project_row["duration_seconds"]) if project_row["duration_seconds"] else None
    mode = "llm" if highlight_engine.adapter.has_api_key else "heuristic_offline"

    worker_thread = threading.Thread(
        target=_background_highlight_worker,
        args=(project_id, video_duration),
        daemon=True,
    )
    worker_thread.start()

    return HighlightStartResponse(
        status="ACCEPTED",
        project_id=project_id,
        mode=mode,
        message=f"Highlight discovery initiated in background ({mode} mode).",
    )


@router.get(
    "/{project_id}/highlights/status",
    response_model=HighlightStatusResponse,
)
def get_highlight_status(project_id: str):
    """Retrieve highlight discovery status and progress."""
    # Check if project exists
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM projects WHERE id = ?;", (project_id,))
        p_row = cursor.fetchone()
        if not p_row:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

        # Count existing clips in database
        cursor.execute("SELECT COUNT(*) as cnt FROM clips WHERE project_id = ?;", (project_id,))
        count_row = cursor.fetchone()
        candidate_count = count_row["cnt"] if count_row else 0

    mode = "llm" if highlight_engine.adapter.has_api_key else "heuristic_offline"

    with _jobs_lock:
        job = _active_jobs.get(project_id)
        if job:
            is_running = job["status"] == "IN_PROGRESS"
            return HighlightStatusResponse(
                project_id=project_id,
                status=job["status"],
                progress_percent=job["progress_percent"],
                candidate_count=job.get("candidate_count", candidate_count),
                mode=job.get("mode", mode),
                error=job.get("error"),
                is_running=is_running,
            )

    # If no in-memory job, infer from project status
    proj_status = p_row["status"]
    if proj_status == "HIGHLIGHTS_READY":
        return HighlightStatusResponse(
            project_id=project_id,
            status="COMPLETED",
            progress_percent=100,
            candidate_count=candidate_count,
            mode=mode,
            error=None,
            is_running=False,
        )

    return HighlightStatusResponse(
        project_id=project_id,
        status="IDLE",
        progress_percent=0,
        candidate_count=candidate_count,
        mode=mode,
        error=None,
        is_running=False,
    )


@router.get(
    "/{project_id}/highlights",
    response_model=List[ClipModel],
)
def get_project_highlights(project_id: str):
    """Retrieve all discovered highlight clips for a project."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM projects WHERE id = ?;", (project_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

        cursor.execute(
            """
            SELECT * FROM clips 
            WHERE project_id = ? 
            ORDER BY engagement_score DESC, start_time ASC;
            """,
            (project_id,),
        )
        rows = cursor.fetchall()

    clips = []
    for r in rows:
        clips.append(
            ClipModel(
                id=r["id"],
                project_id=r["project_id"],
                start_word_index=int(r["start_word_index"]),
                end_word_index=int(r["end_word_index"]),
                start_time=float(r["start_time"]),
                end_time=float(r["end_time"]),
                title=r["title"],
                hook=r["hook"] or "",
                description=r["description"] or "",
                rationale=r["rationale"] or "",
                category=r["category"] or "general",
                engagement_score=float(r["engagement_score"]),
                validation_status=r["validation_status"] or "VALID",
                validation_reason=r["validation_reason"] or "",
                selected=bool(r["selected"]),
                status=r["status"] or "DISCOVERED",
            )
        )
    return clips


@router.get(
    "/{project_id}/highlights/{candidate_id}",
    response_model=ClipModel,
)
def get_single_highlight(project_id: str, candidate_id: str):
    """Retrieve details for a single highlight clip."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM clips WHERE project_id = ? AND id = ?;",
            (project_id, candidate_id),
        )
        r = cursor.fetchone()
        if not r:
            raise HTTPException(
                status_code=404,
                detail=f"Clip candidate '{candidate_id}' not found in project '{project_id}'.",
            )

    return ClipModel(
        id=r["id"],
        project_id=r["project_id"],
        start_word_index=int(r["start_word_index"]),
        end_word_index=int(r["end_word_index"]),
        start_time=float(r["start_time"]),
        end_time=float(r["end_time"]),
        title=r["title"],
        hook=r["hook"] or "",
        description=r["description"] or "",
        rationale=r["rationale"] or "",
        category=r["category"] or "general",
        engagement_score=float(r["engagement_score"]),
        validation_status=r["validation_status"] or "VALID",
        validation_reason=r["validation_reason"] or "",
        selected=bool(r["selected"]),
        status=r["status"] or "DISCOVERED",
    )


@router.patch(
    "/{project_id}/highlights/{candidate_id}",
    response_model=ClipModel,
)
def update_highlight_candidate(
    project_id: str,
    candidate_id: str,
    patch: ClipPatchRequest,
):
    """Update a highlight candidate's selection toggle, title, or status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM clips WHERE project_id = ? AND id = ?;",
            (project_id, candidate_id),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Clip candidate '{candidate_id}' not found in project '{project_id}'.",
            )

        updates = []
        params = []
        if patch.selected is not None:
            updates.append("selected = ?")
            params.append(1 if patch.selected else 0)
        if patch.title is not None:
            updates.append("title = ?")
            params.append(patch.title.strip())
        if patch.status is not None:
            updates.append("status = ?")
            params.append(patch.status.strip())

        if updates:
            sql = f"UPDATE clips SET {', '.join(updates)} WHERE project_id = ? AND id = ?;"
            params.extend([project_id, candidate_id])
            cursor.execute(sql, tuple(params))
            conn.commit()

        # Re-fetch updated row
        cursor.execute(
            "SELECT * FROM clips WHERE project_id = ? AND id = ?;",
            (project_id, candidate_id),
        )
        r = cursor.fetchone()

    # Also update candidates.json disk artifact if it exists
    candidates_file = settings.data_dir / "projects" / project_id / "work" / "candidates.json"
    if candidates_file.exists():
        try:
            with open(candidates_file, "r", encoding="utf-8") as f:
                disk_data = json.load(f)
            for c in disk_data.get("clips", []):
                if c.get("id") == candidate_id:
                    if patch.selected is not None:
                        c["selected"] = patch.selected
                    if patch.title is not None:
                        c["title"] = patch.title.strip()
                    if patch.status is not None:
                        c["status"] = patch.status.strip()
            with open(candidates_file, "w", encoding="utf-8") as f:
                json.dump(disk_data, f, indent=2)
        except Exception as e:
            logger.warning(f"[HighlightsRoute] Could not sync patch to {candidates_file}: {e}")

    return ClipModel(
        id=r["id"],
        project_id=r["project_id"],
        start_word_index=int(r["start_word_index"]),
        end_word_index=int(r["end_word_index"]),
        start_time=float(r["start_time"]),
        end_time=float(r["end_time"]),
        title=r["title"],
        hook=r["hook"] or "",
        description=r["description"] or "",
        rationale=r["rationale"] or "",
        category=r["category"] or "general",
        engagement_score=float(r["engagement_score"]),
        validation_status=r["validation_status"] or "VALID",
        validation_reason=r["validation_reason"] or "",
        selected=bool(r["selected"]),
        status=r["status"] or "DISCOVERED",
    )

