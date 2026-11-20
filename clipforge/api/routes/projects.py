"""Projects and Video Ingestion API Router.

Handles secure video upload, streaming writes, format validation,
FFprobe metadata extraction, range-based media playback streaming,
and audio extraction dispatch.
"""

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Header, UploadFile, status
from fastapi.responses import StreamingResponse

from clipforge.core.config import settings
from clipforge.core.logging import logger
from clipforge.db.models import ProjectModel
from clipforge.db.session import get_db_connection
from clipforge.media.ffmpeg import (
    SUPPORTED_VIDEO_EXTENSIONS,
    FFmpegError,
    FFmpegNotFoundError,
    InvalidMediaFileError,
    NoAudioStreamError,
    ffmpeg_engine,
    is_valid_media_header,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and invalid filesystem characters."""
    base = os.path.basename(filename)
    clean = re.sub(r"[^\w\.\-]", "_", base)
    clean = re.sub(r"\.{2,}", ".", clean)  # remove consecutive dots
    return clean.strip("._") or f"video_{uuid.uuid4().hex[:8]}.mp4"


def stream_media_file(file_path: Path, range_header: Optional[str] = None) -> StreamingResponse:
    """Serve media files with HTTP 206 Partial Content (Range requests) support."""
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Media file not found on disk.")

    file_size = file_path.stat().st_size
    ext = file_path.suffix.lower()
    content_type_map = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
    }
    content_type = content_type_map.get(ext, "application/octet-stream")

    if not range_header or not range_header.startswith("bytes="):
        def iter_full():
            with open(file_path, "rb") as f:
                while chunk := f.read(256 * 1024):
                    yield chunk

        return StreamingResponse(
            iter_full(),
            status_code=status.HTTP_200_OK,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
            },
        )

    # Parse range header: e.g. "bytes=0-1048575" or "bytes=500-"
    try:
        range_spec = range_header.replace("bytes=", "").strip()
        parts = range_spec.split("-", 1)
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        if start > end or start >= file_size:
            raise ValueError("Invalid range boundary")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail=f"Requested range unsatisfiable for file of size {file_size} bytes.",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    content_length = end - start + 1

    def iter_partial():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_size = min(256 * 1024, remaining)
                data = f.read(chunk_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        iter_partial(),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        headers={
            "Content-Type": content_type,
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Accept-Ranges": "bytes",
        },
    )


@router.post("/upload", response_model=ProjectModel, status_code=status.HTTP_201_CREATED)
def upload_video(file: UploadFile = File(...)) -> ProjectModel:
    """Upload a video file with chunked streaming, format validation, and metadata extraction."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    sanitized = sanitize_filename(file.filename)
    ext = Path(sanitized).suffix.lower()

    if ext not in SUPPORTED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(SUPPORTED_VIDEO_EXTENSIONS))}",
        )

    project_id = str(uuid.uuid4())
    project_dir = settings.projects_dir / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    target_path = project_dir / f"source_{sanitized}"

    # Streaming write with size protection and magic byte validation
    bytes_written = 0
    first_chunk = True

    try:
        with open(target_path, "wb") as dest:
            while True:
                # Read chunks directly from underlying file stream to avoid anyio thread deadlocks on Windows
                chunk = file.file.read(64 * 1024)
                if not chunk:
                    break

                if first_chunk:
                    first_chunk = False
                    if not is_valid_media_header(chunk, ext):
                        raise InvalidMediaFileError(
                            f"File header signature does not match expected {ext} video container format."
                        )

                bytes_written += len(chunk)
                if bytes_written > settings.max_upload_size_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=(
                            f"File exceeds maximum configured upload limit of "
                            f"{settings.max_upload_size_bytes / (1024 * 1024):.0f} MB."
                        ),
                    )
                dest.write(chunk)

        if bytes_written == 0:
            raise HTTPException(status_code=400, detail="Uploaded video file is empty (0 bytes).")

    except (InvalidMediaFileError, HTTPException) as e:
        # Clean up partial upload
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        if project_dir.exists() and not any(project_dir.iterdir()):
            project_dir.rmdir()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during video upload write: {e}")
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        if project_dir.exists() and not any(project_dir.iterdir()):
            project_dir.rmdir()
        raise HTTPException(status_code=500, detail=f"Failed to save video: {e}")

    # Inspect metadata using FFprobe
    duration_seconds = 0.0
    width = 0
    height = 0
    fps = 0.0
    video_codec = ""
    audio_codec = ""
    has_audio = False
    container_format = ext.lstrip(".")
    current_status = "INGESTED"

    try:
        if ffmpeg_engine.is_ffprobe_available():
            meta = ffmpeg_engine.probe_metadata(target_path)
            duration_seconds = meta["duration_seconds"]
            width = meta["width"]
            height = meta["height"]
            fps = meta["fps"]
            video_codec = meta["video_codec"]
            audio_codec = meta["audio_codec"]
            has_audio = meta["has_audio"]
            container_format = meta["container_format"]
        else:
            logger.warning(f"FFprobe not available. Storing basic file attributes for {sanitized}.")
            file_size_bytes = target_path.stat().st_size
    except Exception as e:
        logger.warning(f"Metadata probe failed for {sanitized}: {e}")
        current_status = "PROBING_FAILED"

    # Persist in database
    now = datetime.utcnow()
    project = ProjectModel(
        id=project_id,
        title=Path(sanitized).stem.replace("_", " ").title(),
        source_file_path=str(target_path.resolve()),
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        fps=fps,
        video_codec=video_codec,
        audio_codec=audio_codec,
        has_audio=has_audio,
        file_size_bytes=bytes_written,
        container_format=container_format,
        status=current_status,
        created_at=now,
        updated_at=now,
    )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO projects (
                id, title, source_file_path, duration_seconds, width, height, fps,
                video_codec, audio_codec, has_audio, file_size_bytes, container_format,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                project.id,
                project.title,
                project.source_file_path,
                project.duration_seconds,
                project.width,
                project.height,
                project.fps,
                project.video_codec,
                project.audio_codec,
                1 if project.has_audio else 0,
                project.file_size_bytes,
                project.container_format,
                project.status,
                now.isoformat(),
                now.isoformat(),
            ),
        )
        conn.commit()

    logger.info(f"Video successfully ingested: project_id={project.id}, file={sanitized}, size={bytes_written} bytes")
    return project


@router.get("", response_model=List[ProjectModel])
def list_projects() -> List[ProjectModel]:
    """Retrieve all video projects sorted by creation date."""
    projects: List[ProjectModel] = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY created_at DESC;")
        rows = cursor.fetchall()
        for row in rows:
            projects.append(
                ProjectModel(
                    id=row["id"],
                    title=row["title"],
                    source_file_path=row["source_file_path"],
                    duration_seconds=row["duration_seconds"] or 0.0,
                    width=row["width"] or 0,
                    height=row["height"] or 0,
                    fps=row["fps"] or 0.0,
                    video_codec=row["video_codec"] or "",
                    audio_codec=row["audio_codec"] or "",
                    has_audio=bool(row["has_audio"]),
                    file_size_bytes=row["file_size_bytes"] or 0,
                    container_format=row["container_format"] or "",
                    status=row["status"] or "CREATED",
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                    updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
                )
            )
    return projects


@router.get("/{project_id}", response_model=ProjectModel)
def get_project(project_id: str) -> ProjectModel:
    """Retrieve a single project by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?;", (project_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

        return ProjectModel(
            id=row["id"],
            title=row["title"],
            source_file_path=row["source_file_path"],
            duration_seconds=row["duration_seconds"] or 0.0,
            width=row["width"] or 0,
            height=row["height"] or 0,
            fps=row["fps"] or 0.0,
            video_codec=row["video_codec"] or "",
            audio_codec=row["audio_codec"] or "",
            has_audio=bool(row["has_audio"]),
            file_size_bytes=row["file_size_bytes"] or 0,
            container_format=row["container_format"] or "",
            status=row["status"] or "CREATED",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )


@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
def delete_project(project_id: str):
    """Delete a project and its workspace disk assets."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT source_file_path FROM projects WHERE id = ?;", (project_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

        cursor.execute("DELETE FROM projects WHERE id = ?;", (project_id,))
        conn.commit()

    # Safely delete project folder inside clipforge-data/projects/
    project_dir = (settings.projects_dir / project_id).resolve()
    if project_dir.exists() and str(project_dir).startswith(str(settings.projects_dir.resolve())):
        import shutil
        shutil.rmtree(project_dir, ignore_errors=True)
        logger.info(f"Deleted project disk assets at {project_dir}")

    return {"deleted": True, "project_id": project_id}


@router.get("/{project_id}/stream")
def stream_project_video(
    project_id: str,
    range: Optional[str] = Header(None),
):
    """Stream project video file with range-request support for native HTML5 video player."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT source_file_path FROM projects WHERE id = ?;", (project_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    source_path = Path(row["source_file_path"]).resolve()

    # Security check: ensure path is strictly within settings.projects_dir
    allowed_root = settings.projects_dir.resolve()
    if not str(source_path).startswith(str(allowed_root)):
        logger.warning(f"Arbitrary path traversal blocked: {source_path}")
        raise HTTPException(status_code=403, detail="Access to specified path is forbidden.")

    return stream_media_file(source_path, range_header=range)


@router.post("/{project_id}/extract-audio")
def extract_project_audio(project_id: str):
    """Extract standardized 16kHz mono audio WAV for upcoming Whisper transcription."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?;", (project_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    source_path = Path(row["source_file_path"]).resolve()
    project_dir = settings.projects_dir / project_id
    output_audio_path = project_dir / "audio_16k.wav"

    if not ffmpeg_engine.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FFmpeg binary is not installed or available on this system.",
        )

    try:
        audio_file = ffmpeg_engine.extract_audio(
            source_video_path=source_path,
            output_audio_path=output_audio_path,
            sample_rate=16000,
            channels=1,
        )

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE projects SET status = 'AUDIO_READY', updated_at = ? WHERE id = ?;",
                (datetime.utcnow().isoformat(), project_id),
            )
            conn.commit()

        return {
            "status": "AUDIO_READY",
            "project_id": project_id,
            "audio_file_path": str(audio_file.resolve()),
            "sample_rate": 16000,
            "channels": 1,
        }

    except NoAudioStreamError as e:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE projects SET status = 'NO_AUDIO', updated_at = ? WHERE id = ?;",
                (datetime.utcnow().isoformat(), project_id),
            )
            conn.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Video does not contain an audio track: {e}",
        )
    except FFmpegNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except FFmpegError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
