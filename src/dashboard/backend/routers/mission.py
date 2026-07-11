"""
Mission Router — mission control REST endpoints.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from src.core.types import GeotaggedDetection
from src.dashboard.backend.dependencies import container
from src.dashboard.backend.models.schemas import (
    MissionStatus, MissionStartRequest, MissionCommandResponse,
)
from src.mission.waypoint_planner import WaypointPlanner, PatternRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mission", tags=["mission"])


@router.post("/start", response_model=MissionCommandResponse)
async def start_mission(req: MissionStartRequest):
    """Start an autonomous inspection mission."""
    sm = container.state_machine
    config = container.config
    mission_cfg = config.get("mission", {})
    search_area = mission_cfg.get("search_area", {})

    if sm.current_state != "IDLE":
        raise HTTPException(
            400, f"Cannot start: currently in {sm.current_state}",
        )

    # Build pattern config
    center_lat = req.center_lat or search_area.get("center_lat", 47.397742)
    center_lon = req.center_lon or search_area.get("center_lon", 8.545594)

    pattern_config = {
        "center_lat": center_lat,
        "center_lon": center_lon,
        "width_m": req.width_m,
        "height_m": req.height_m,
        "spacing_m": req.spacing_m,
        "altitude_m": req.altitude_m,
        "initial_radius_m": 20,
        "expansion_m": 15,
        "max_radius_m": 100,
    }

    try:
        waypoints = PatternRegistry.generate(req.pattern, pattern_config)
    except ValueError:
        waypoints = PatternRegistry.generate("lawnmower", pattern_config)

    # Clear previous detections
    container.detections = []

    # Register detection callback
    async def on_detection(det: GeotaggedDetection):
        container.detections.append(det)

    sm.set_callbacks(on_detection=on_detection)

    # Run mission in background
    container.mission_task = asyncio.create_task(
        sm.run_mission(waypoints),
    )

    return MissionCommandResponse(
        success=True,
        message=(
            f"Mission started with {len(waypoints)} waypoints "
            f"({req.pattern})"
        ),
        state=sm.current_state,
    )


@router.post("/abort", response_model=MissionCommandResponse)
async def abort_mission():
    """Abort the current mission and RTL."""
    sm = container.state_machine
    if sm.current_state == "IDLE":
        return MissionCommandResponse(
            success=False, message="No active mission", state="IDLE",
        )
    await sm.request_abort()
    return MissionCommandResponse(
        success=True,
        message="Abort commanded — returning to launch",
        state=sm.current_state,
    )


@router.post("/rtl", response_model=MissionCommandResponse)
async def rtl():
    """Command Return to Launch."""
    flight = container.flight
    sm = container.state_machine
    try:
        await flight.rtl()
        return MissionCommandResponse(
            success=True, message="RTL commanded",
            state=sm.current_state,
        )
    except Exception as e:
        raise HTTPException(500, f"RTL failed: {e}")


@router.get("/status", response_model=MissionStatus)
async def mission_status():
    """Get current mission status."""
    sm = container.state_machine
    connector = container.connector
    telem = connector.latest_telemetry

    return MissionStatus(
        state=sm.current_state,
        elapsed_seconds=sm.mission_elapsed_s,
        waypoints_total=len(sm.waypoints),
        waypoints_completed=sm.current_waypoint_index,
        detections_count=len(container.detections),
        battery_percent=telem.battery_percent if telem else 100,
        is_connected=connector.is_connected,
    )
