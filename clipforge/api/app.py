"""FastAPI Application Factory & Lifecycle Management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from clipforge.core.config import settings
from clipforge.core.logging import logger
from clipforge.db.session import init_db, reconcile_interrupted_jobs
from clipforge.api.routes.health import router as health_router
from clipforge.api.routes.projects import router as projects_router
from clipforge.api.routes.transcription import router as transcription_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan event handler."""
    logger.info("Initializing ClipForge AI application...")
    settings.ensure_directories()
    init_db()
    reconciled = reconcile_interrupted_jobs()
    if reconciled > 0:
        logger.info(f"Startup reconciliation: marked {reconciled} interrupted job(s) as FAILED.")
    logger.info("Database and storage directories initialized.")
    yield
    logger.info("Shutting down ClipForge AI application...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Local-first desktop-optimized AI video clipping engine.",
        lifespan=lifespan,
    )

    # Configure CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(health_router, prefix="/api")
    app.include_router(projects_router, prefix="/api")
    app.include_router(transcription_router, prefix="/api")

    # Root redirect / friendly ping
    @app.get("/")
    def root():
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "status": "online",
            "docs_url": "/docs",
            "health_url": "/api/health",
        }

    return app


app = create_app()

