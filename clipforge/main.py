"""Application Entry Point CLI.

Starts the FastAPI server with uvicorn.
"""

import sys
import uvicorn
from clipforge.core.config import settings
from clipforge.core.logging import logger


def run() -> None:
    """Launch the uvicorn server."""
    logger.info(
        f"Starting {settings.app_name} v{settings.app_version} on {settings.host}:{settings.port}"
    )
    uvicorn.run(
        "clipforge.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )


if __name__ == "__main__":
    run()

