"""Health Check & System Diagnostic Routes."""

from datetime import datetime, timezone
import sqlite3
from typing import Dict, Any
from fastapi import APIRouter
from clipforge.core.config import settings
from clipforge.core.hardware import get_hardware_profile
from clipforge.db.session import get_db_connection
from clipforge.media.ffmpeg import FFmpegInterface

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/health")
def health_check() -> Dict[str, Any]:
    """Basic health check and runtime diagnostic endpoint."""
    # Check SQLite connectivity
    db_status = "disconnected"
    journal_mode = "unknown"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            row = cursor.fetchone()
            if row:
                journal_mode = row[0]
                db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check FFmpeg availability
    ffmpeg_tool = FFmpegInterface()
    ffmpeg_info = ffmpeg_tool.get_version_info()

    # Hardware profile
    hw_profile = get_hardware_profile()

    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": db_status,
            "path": str(settings.db_path),
            "journal_mode": journal_mode,
        },
        "hardware": hw_profile,
        "media_tools": {
            "ffmpeg_available": ffmpeg_tool.is_available(),
            "ffprobe_available": ffmpeg_tool.is_ffprobe_available(),
            "details": ffmpeg_info,
        },
    }

