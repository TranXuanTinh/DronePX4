"""
Dashboard Backend — FastAPI application entry point.

Provides REST and WebSocket endpoints for the operator dashboard:
- Real-time telemetry streaming (WebSocket)
- Live detection events (WebSocket)
- Live video with overlays (WebSocket MJPEG)
- Mission control (start, abort, RTL)
- Detection log and reports (PDF / CSV)
"""

import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config_loader import load_config
from src.utils.logger import setup_logging
from src.bridge.mavlink_bridge import MAVLinkBridge, TelemetryFrame
from src.bridge.commands import FlightCommands
from src.bridge.telemetry import TelemetryCollector
from src.perception.camera import GazeboCamera
from src.perception.detector import YOLODetector
from src.perception.tracker import ByteTrackWrapper
from src.perception.geotagging import GPSGeotagger, GeotaggedDetection
from src.streaming.video_server import VideoServer
from src.streaming.overlay import DetectionOverlay
from src.mission.state_machine import MissionStateMachine
from src.mission.safety import SafetyMonitor
from src.mission.waypoint_planner import WaypointPlanner
from src.dashboard.backend.models.schemas import (
    TelemetryData, DetectionEvent, DetectionListResponse,
    MissionStatus, MissionStartRequest, MissionCommandResponse,
    SystemStatus, BoundingBox,
)

logger = logging.getLogger(__name__)

# === Global state (initialized in lifespan) ===
app_state = {
    "bridge": None,
    "commands": None,
    "telemetry_collector": None,
    "camera": None,
    "detector": None,
    "tracker": None,
    "geotagger": None,
    "video_server": None,
    "state_machine": None,
    "safety": None,
    "config": None,
    "detections": [],
    "mission_task": None,
    "start_time": time.time(),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize subsystems on startup, cleanup on shutdown."""
    config = load_config()
    setup_logging(level=config.get("logging", {}).get("level", "INFO"))
    app_state["config"] = config
    app_state["start_time"] = time.time()

    logger.info("Dashboard backend starting...")

    # --- Bridge ---
    bridge = MAVLinkBridge(
        connection_string=config.get("connection", {}).get("mavsdk_address")
    )
    try:
        await bridge.connect()
        await bridge.wait_for_ready()
        logger.info("Connected to PX4 SITL")
    except Exception as e:
        logger.warning(f"Could not connect to PX4 SITL: {e}. Running in offline mode.")

    app_state["bridge"] = bridge
    app_state["commands"] = FlightCommands(bridge)

    # --- Telemetry ---
    telemetry_collector = TelemetryCollector(bridge)
    try:
        await telemetry_collector.start(
            rate_hz=config.get("dashboard", {}).get("telemetry_rate_hz", 10)
        )
    except Exception as e:
        logger.warning(f"Telemetry start failed: {e}")
    app_state["telemetry_collector"] = telemetry_collector

    # --- Camera ---
    cam_cfg = config.get("camera", {})
    camera = GazeboCamera(
        source=cam_cfg.get("source", "gazebo"),
        width=cam_cfg.get("width", 640),
        height=cam_cfg.get("height", 480),
    )
    camera.open()
    app_state["camera"] = camera

    # --- Perception ---
    perc_cfg = config.get("perception", {})
    detector = YOLODetector(
        model_path=perc_cfg.get("model", "yolov8s.pt"),
        device=perc_cfg.get("device", "cpu"),
        conf_thresh=perc_cfg.get("confidence_threshold", 0.45),
        target_classes=perc_cfg.get("classes"),
    )
    try:
        detector.load()
    except Exception as e:
        logger.warning(f"Detector load failed: {e}")
    app_state["detector"] = detector

    trk_cfg = perc_cfg.get("tracker", {})
    tracker = ByteTrackWrapper(
        track_thresh=trk_cfg.get("track_thresh", 0.5),
        match_thresh=trk_cfg.get("match_thresh", 0.8),
        track_buffer=trk_cfg.get("track_buffer", 30),
    )
    app_state["tracker"] = tracker

    geotagger = GPSGeotagger(
        camera_hfov_deg=cam_cfg.get("hfov_deg", 60),
        image_width=cam_cfg.get("width", 640),
        image_height=cam_cfg.get("height", 480),
    )
    app_state["geotagger"] = geotagger

    # --- Video Server ---
    overlay = DetectionOverlay()
    video_server = VideoServer(
        camera=camera, overlay=overlay,
        jpeg_quality=config.get("dashboard", {}).get("video_quality", 70),
    )
    app_state["video_server"] = video_server
    asyncio.create_task(video_server.stream_loop())

    # --- Safety ---
    safety_cfg = config.get("safety", {})
    mission_cfg = config.get("mission", {})
    search_area = mission_cfg.get("search_area", {})
    safety = SafetyMonitor(
        geofence_radius_m=safety_cfg.get("geofence_radius_m", 500),
        max_altitude_m=safety_cfg.get("max_altitude_m", 120),
        min_battery_pct=safety_cfg.get("min_battery_percent", 20),
        critical_battery_pct=safety_cfg.get("critical_battery_percent", 10),
        home_lat=search_area.get("center_lat", 47.397742),
        home_lon=search_area.get("center_lon", 8.545594),
    )
    app_state["safety"] = safety

    # --- State Machine ---
    sm = MissionStateMachine(
        bridge=bridge, commands=app_state["commands"],
        detector=detector, tracker=tracker,
        geotagger=geotagger, camera=camera,
        safety=safety, config=mission_cfg,
    )
    app_state["state_machine"] = sm

    logger.info("Dashboard backend ready")
    yield

    # Cleanup
    logger.info("Shutting down...")
    video_server.stop()
    camera.release()
    await telemetry_collector.stop()
    await bridge.disconnect()


app = FastAPI(
    title="Drone Inspector Dashboard",
    description="Operator dashboard for autonomous inspection drone simulation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================================================================
# REST Endpoints
# ================================================================

@app.get("/api/status", response_model=SystemStatus)
async def get_status():
    """Get system health and connection status."""
    bridge: MAVLinkBridge = app_state["bridge"]
    sm: MissionStateMachine = app_state["state_machine"]
    detector: YOLODetector = app_state["detector"]
    telem = bridge.latest_telemetry

    return SystemStatus(
        sitl_connected=bridge.is_connected,
        flight_mode=telem.flight_mode if telem else "UNKNOWN",
        armed=telem.armed if telem else False,
        gps_fix=telem.gps_fix_type >= 3 if telem else False,
        battery_percent=telem.battery_percent if telem else 0,
        mission_state=sm.current_state if sm else "IDLE",
        uptime_seconds=time.time() - app_state["start_time"],
        detection_count=len(app_state["detections"]),
        avg_inference_ms=detector.avg_inference_ms if detector else 0,
    )


@app.get("/api/detections", response_model=DetectionListResponse)
async def get_detections():
    """Get all detection events from the current/last mission."""
    events = []
    for i, d in enumerate(app_state["detections"]):
        events.append(DetectionEvent(
            id=f"DET-{i+1:03d}",
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


@app.post("/api/mission/start", response_model=MissionCommandResponse)
async def start_mission(req: MissionStartRequest):
    """Start an autonomous inspection mission."""
    sm: MissionStateMachine = app_state["state_machine"]
    config = app_state["config"]
    mission_cfg = config.get("mission", {})
    search_area = mission_cfg.get("search_area", {})

    if sm.current_state != "IDLE":
        raise HTTPException(400, f"Cannot start: currently in {sm.current_state}")

    # Generate waypoints
    center_lat = req.center_lat or search_area.get("center_lat", 47.397742)
    center_lon = req.center_lon or search_area.get("center_lon", 8.545594)

    if req.pattern == "lawnmower":
        waypoints = WaypointPlanner.lawnmower(
            center_lat, center_lon,
            req.width_m, req.height_m, req.spacing_m, req.altitude_m,
        )
    elif req.pattern == "expanding_square":
        waypoints = WaypointPlanner.expanding_square(
            center_lat, center_lon,
            initial_radius_m=20, expansion_m=15,
            max_radius_m=100, altitude_m=req.altitude_m,
        )
    else:
        waypoints = WaypointPlanner.lawnmower(
            center_lat, center_lon, 100, 100, 20, req.altitude_m,
        )

    # Clear previous detections
    app_state["detections"] = []

    # Register detection callback
    async def on_detection(det: GeotaggedDetection):
        app_state["detections"].append(det)

    sm.set_callbacks(on_detection=on_detection)

    # Run mission in background
    app_state["mission_task"] = asyncio.create_task(sm.run_mission(waypoints))

    return MissionCommandResponse(
        success=True,
        message=f"Mission started with {len(waypoints)} waypoints ({req.pattern})",
        state=sm.current_state,
    )


@app.post("/api/mission/abort", response_model=MissionCommandResponse)
async def abort_mission():
    """Abort the current mission and RTL."""
    sm: MissionStateMachine = app_state["state_machine"]

    if sm.current_state == "IDLE":
        return MissionCommandResponse(success=False, message="No active mission", state="IDLE")

    await sm.request_abort()
    return MissionCommandResponse(
        success=True, message="Abort commanded — returning to launch",
        state=sm.current_state,
    )


@app.post("/api/mission/rtl", response_model=MissionCommandResponse)
async def rtl():
    """Command Return to Launch."""
    commands: FlightCommands = app_state["commands"]
    sm: MissionStateMachine = app_state["state_machine"]

    try:
        await commands.rtl()
        return MissionCommandResponse(
            success=True, message="RTL commanded", state=sm.current_state,
        )
    except Exception as e:
        raise HTTPException(500, f"RTL failed: {e}")


@app.get("/api/mission/status", response_model=MissionStatus)
async def mission_status():
    """Get current mission status."""
    sm: MissionStateMachine = app_state["state_machine"]
    bridge: MAVLinkBridge = app_state["bridge"]
    telem = bridge.latest_telemetry

    return MissionStatus(
        state=sm.current_state,
        elapsed_seconds=sm.mission_elapsed_s,
        waypoints_total=len(sm.waypoints),
        waypoints_completed=sm.current_waypoint_index,
        detections_count=len(app_state["detections"]),
        battery_percent=telem.battery_percent if telem else 100,
        is_connected=bridge.is_connected,
    )


@app.get("/api/report/csv")
async def generate_csv_report():
    """Generate and download CSV detection report."""
    import csv
    import io

    detections = app_state["detections"]
    if not detections:
        raise HTTPException(404, "No detections to report")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "timestamp", "detection_id", "track_id", "class",
        "confidence", "latitude", "longitude", "altitude_m",
    ])
    for i, d in enumerate(detections):
        writer.writerow([
            d.timestamp, f"DET-{i+1:03d}", d.track_id, d.class_name,
            f"{d.confidence:.3f}", f"{d.latitude_deg:.6f}",
            f"{d.longitude_deg:.6f}", f"{d.drone_altitude_m:.1f}",
        ])

    report_dir = Path(app_state["config"].get("logging", {}).get("report_dir", "data/reports"))
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "detection_report.csv"
    report_path.write_text(output.getvalue())

    return FileResponse(
        path=str(report_path),
        media_type="text/csv",
        filename="detection_report.csv",
    )


@app.get("/api/report/pdf")
async def generate_pdf_report():
    """Generate and download PDF mission report."""
    from src.dashboard.backend.api.reports import generate_pdf

    detections = app_state["detections"]
    sm: MissionStateMachine = app_state["state_machine"]
    config = app_state["config"]

    report_dir = Path(config.get("logging", {}).get("report_dir", "data/reports"))
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "mission_report.pdf"

    try:
        generate_pdf(
            output_path=str(report_path),
            detections=detections,
            mission_duration_s=sm.mission_elapsed_s,
            waypoint_count=len(sm.waypoints),
        )
        return FileResponse(
            path=str(report_path),
            media_type="application/pdf",
            filename="mission_report.pdf",
        )
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}")


@app.get("/api/snapshot")
async def get_snapshot():
    """Get a single JPEG snapshot from the camera."""
    from fastapi.responses import Response
    video_server: VideoServer = app_state["video_server"]
    data = video_server.get_snapshot()
    if data is None:
        raise HTTPException(503, "Camera not available")
    return Response(content=data, media_type="image/jpeg")


# ================================================================
# WebSocket Endpoints
# ================================================================

@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    """Stream real-time telemetry at 10 Hz."""
    await websocket.accept()
    logger.info("Telemetry WebSocket client connected")

    collector: TelemetryCollector = app_state["telemetry_collector"]
    sm: MissionStateMachine = app_state["state_machine"]
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


@app.websocket("/ws/detections")
async def ws_detections(websocket: WebSocket):
    """Stream detection events in real-time."""
    await websocket.accept()
    logger.info("Detections WebSocket client connected")

    last_count = 0
    try:
        while True:
            current_count = len(app_state["detections"])
            if current_count > last_count:
                # Send new detections
                for i in range(last_count, current_count):
                    d = app_state["detections"][i]
                    event = DetectionEvent(
                        id=f"DET-{i+1:03d}",
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


@app.websocket("/ws/video")
async def ws_video(websocket: WebSocket):
    """Stream MJPEG video frames with detection overlays."""
    await websocket.accept()
    video_server: VideoServer = app_state["video_server"]

    await video_server.register_client(websocket)
    try:
        while True:
            # Keep connection alive; frames are pushed by video_server
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await video_server.unregister_client(websocket)


# ================================================================
# Main
# ================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.dashboard.backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
