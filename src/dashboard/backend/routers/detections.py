"""
Detections Router — detection log REST + WebSocket endpoints.
"""
from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.dashboard.backend.dependencies import container
from src.dashboard.backend.models.schemas import (
    DetectionEvent, DetectionListResponse, BoundingBox,
    SystemStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["detections"])


@router.get("/api/status", response_model=SystemStatus)
async def get_status():
    """Get system health and connection status."""
    connector = container.connector
    sm = container.state_machine
    detector = container.detector
    telem = connector.latest_telemetry if connector else None

    return SystemStatus(
        sitl_connected=connector.is_connected if connector else False,
        flight_mode=telem.flight_mode if telem else "UNKNOWN",
        armed=telem.armed if telem else False,
        gps_fix=telem.gps_fix_type >= 3 if telem else False,
        battery_percent=telem.battery_percent if telem else 0,
        mission_state=sm.current_state if sm else "IDLE",
        uptime_seconds=time.time() - container.start_time,
        detection_count=len(container.detections),
        avg_inference_ms=detector.avg_inference_ms if detector else 0,
    )


@router.get("/api/detections", response_model=DetectionListResponse)
async def get_detections():
    """Get all detection events from the current/last mission."""
    events = []
    for i, d in enumerate(container.detections):
        events.append(DetectionEvent(
            id=f"DET-{i + 1:03d}",
            timestamp=d.timestamp,
            track_id=d.track_id,
            class_name=d.class_name,
            confidence=d.confidence,
            latitude=d.latitude_deg,
            longitude=d.longitude_deg,
            altitude_m=d.drone_altitude_m,
            bbox=BoundingBox(
                x1=int(d.bbox[0]), y1=int(d.bbox[1]),
                x2=int(d.bbox[2]), y2=int(d.bbox[3]),
            ),
        ))
    return DetectionListResponse(total=len(events), detections=events)


@router.websocket("/ws/detections")
async def ws_detections(websocket: WebSocket):
    """Stream detection events in real-time."""
    await websocket.accept()
    logger.info("Detections WebSocket client connected")

    last_count = 0
    try:
        while True:
            current_count = len(container.detections)

            # Handle list reset between missions (last_count > current_count)
            if current_count < last_count:
                last_count = 0

            if current_count > last_count:
                for i in range(last_count, current_count):
                    d = container.detections[i]
                    event = DetectionEvent(
                        id=f"DET-{i + 1:03d}",
                        timestamp=d.timestamp,
                        track_id=d.track_id,
                        class_name=d.class_name,
                        confidence=d.confidence,
                        latitude=d.latitude_deg,
                        longitude=d.longitude_deg,
                        altitude_m=d.drone_altitude_m,
                        bbox=BoundingBox(
                            x1=int(d.bbox[0]), y1=int(d.bbox[1]),
                            x2=int(d.bbox[2]), y2=int(d.bbox[3]),
                        ),
                    )
                    await websocket.send_json(event.model_dump())
                last_count = current_count
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        logger.info("Detections WebSocket client disconnected")
