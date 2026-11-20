"""Unit tests for the health check and diagnostics endpoint."""

from starlette.routing import Route

from clipforge.api.app import app
from clipforge.api.routes.health import health_check
from clipforge.core.config import settings
from clipforge.db.session import init_db


def test_root_endpoint():
    """Verify the root endpoint definition and response."""
    # Find root route handler
    root_route = next((r for r in app.routes if getattr(r, "path", None) == "/"), None)
    assert isinstance(root_route, Route)
    data = root_route.endpoint()
    assert data["app"] == "ClipForge AI"
    assert data["status"] == "online"
    assert data["health_url"] == "/api/health"


def test_health_check_endpoint(tmp_path):
    """Verify health endpoint returns status, hardware profile, and DB status."""
    # Ensure database is initialized
    init_db(tmp_path / "test_health.db")

    data = health_check()
    assert data["status"] == "healthy"
    assert data["app"] == "ClipForge AI"
    assert "hardware" in data
    assert "database" in data
    assert data["database"]["status"] == "connected"
    assert data["database"]["journal_mode"] == "wal"
    assert "disk_free_gb" in data["hardware"]
    assert "logical_cores" in data["hardware"]
    assert "media_tools" in data
    assert "ffmpeg_available" in data["media_tools"]
