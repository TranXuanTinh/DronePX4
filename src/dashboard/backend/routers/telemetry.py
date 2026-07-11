"""
Telemetry Router — real-time telemetry WebSocket endpoint.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.core.types import TelemetryFrame
from src.dashboard.backend.dependencies import container
from src.dashboard.backend.models.schemas import TelemetryData

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telemetry"])


@router.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    """Stream real-time telemetry at 10 Hz."""
    await websocket.accept()
    logger.info("Telemetry WebSocket client connected")

    collector = container.telemetry_collector
    sm = container.state_machine
    queue = collector.subscribe()

    try:
        while True:
            frame: TelemetryFrame = await queue.get()
            data = TelemetryData(
                timestamp=frame.timestamp,
                latitude=frame.position.latitude_deg,
                longitude=frame.position.longitude_deg,
                altitude_m=frame.position.relative_altitude_m,
                heading_deg=frame.heading_deg,
                groundspeed_ms=frame.groundspeed_ms,
                battery_percent=frame.battery_percent,
                battery_voltage=frame.battery_voltage,
                flight_mode=frame.flight_mode,
                armed=frame.armed,
                gps_satellites=frame.gps_num_satellites,
                gps_fix_type=frame.gps_fix_type,
                mission_state=sm.current_state if sm else "IDLE",
                is_connected=frame.is_connected,
            )
            await websocket.send_json(data.model_dump())
    except WebSocketDisconnect:
        logger.info("Telemetry WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Telemetry WS error: {e}")
    finally:
        collector.unsubscribe(queue)
