"""
Dashboard Backend — FastAPI application (SRP-compliant).

Slim entry point: creates FastAPI app, registers routers,
and manages lifecycle. All logic is in routers/ and dependencies.py.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config_loader import load_config
from src.utils.logger import setup_logging
from src.dashboard.backend.dependencies import container
from src.dashboard.backend.routers import (
    mission, telemetry, detections, video, reports,
)
from src.factory import AppFactory

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize subsystems on startup, cleanup on shutdown."""
    config = load_config()
    setup_logging(level=config.get("logging", {}).get("level", "INFO"))

    logger.info("Dashboard backend starting...")

    # Use the factory to wire all subsystems into the container
    await AppFactory.initialize(container, config)

    logger.info("Dashboard backend ready")
    yield

    # Cleanup
    logger.info("Shutting down...")
    await AppFactory.shutdown(container)


app = FastAPI(
    title="Drone Inspector Dashboard",
    description="Operator dashboard for autonomous inspection drone simulation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(mission.router)
app.include_router(telemetry.router)
app.include_router(detections.router)
app.include_router(video.router)
app.include_router(reports.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.dashboard.backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
