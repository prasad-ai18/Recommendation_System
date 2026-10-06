"""Entrypoint script for launching the Personalized Recommendation Intelligence Platform."""

import os
import sys
import uvicorn
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import settings
from src.logger import logger


def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    logger.info("=" * 70)
    logger.info("STARTING: Personalized Recommendation Intelligence Platform")
    logger.info(f"Host: http://{host}:{port}")
    logger.info(f"API Docs: http://{host}:{port}/docs")
    logger.info("=" * 70)

    uvicorn.run(
        "src.api.app:app",
        host=host,
        port=port,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
