"""
App Factory — centralized subsystem construction.

Eliminates the 70+ lines of manual wiring duplicated across main.py
and run_mission.py. Creates all subsystems from config and wires
them into an AppContainer or returns individual components.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from src.core.events import EventBus
from src.core.types import TelemetryFrame
from src.bridge.mavlink_bridge import MAVLinkBridge
from src.bridge.commands import FlightCommands
from src.bridge.telemetry import TelemetryCollector
from src.perception.camera import CameraFactory
from src.perception.detector import YOLODetector
from src.perception.tracker import ByteTrackWrapper
from src.perception.geotagging import GPSGeotagger
from src.streaming.overlay import DetectionOverlay
from src.streaming.video_server import VideoServer
from src.mission.state_machine import MissionStateMachine
from src.mission.safety import SafetyMonitor

logger = logging.getLogger(__name__)


class AppFactory:
    """Factory for constructing the full application from config.

    Usage (dashboard):
        await AppFactory.initialize(container, config)

    Usage (standalone mission):
        components = AppFactory.create_mission_components(config)
    """

    @staticmethod
    async def initialize(container, config: dict) -> None:
        """Populate an AppContainer with all subsystems.

        Used by the dashboard backend lifespan.
        """
        container.config = config
        container.event_bus = EventBus()

        # --- Bridge ---
        bridge = MAVLinkBridge(
            connection_string=config.get("connection", {}).get(
                "mavsdk_address",
            ),
        )
        try:
            await bridge.connect()
            await bridge.wait_for_ready()
            logger.info("Connected to PX4 SITL")
        except Exception as e:
            logger.warning(
                f"Could not connect to PX4 SITL: {e}. "
                "Running in offline mode."
            )

        container.connector = bridge
        container.flight = FlightCommands(bridge)

        # --- Telemetry ---
        collector = TelemetryCollector(
            bridge, event_bus=container.event_bus,
        )
        try:
            await collector.start(
                rate_hz=config.get("dashboard", {}).get(
                    "telemetry_rate_hz", 10,
                ),
            )
        except Exception as e:
            logger.warning(f"Telemetry start failed: {e}")
        container.telemetry_collector = collector

        # --- Camera ---
        cam_cfg = config.get("camera", {})
        camera = CameraFactory.create(
            source=cam_cfg.get("source", "gazebo"),
            width=cam_cfg.get("width", 640),
            height=cam_cfg.get("height", 480),
        )
        camera.open()
        container.camera = camera

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
        container.detector = detector

        trk_cfg = perc_cfg.get("tracker", {})
        container.tracker = ByteTrackWrapper(
            track_thresh=trk_cfg.get("track_thresh", 0.5),
            match_thresh=trk_cfg.get("match_thresh", 0.8),
            track_buffer=trk_cfg.get("track_buffer", 30),
        )

        container.geotagger = GPSGeotagger(
            camera_hfov_deg=cam_cfg.get("hfov_deg", 60),
            image_width=cam_cfg.get("width", 640),
            image_height=cam_cfg.get("height", 480),
        )

        # --- Video Server ---
        overlay = DetectionOverlay()
        video_server = VideoServer(
            camera=camera, overlay=overlay,
            jpeg_quality=config.get("dashboard", {}).get(
                "video_quality", 70,
            ),
        )
        container.video_server = video_server
        asyncio.create_task(video_server.stream_loop())

        # --- Safety ---
        safety_cfg = config.get("safety", {})
        mission_cfg = config.get("mission", {})
        search_area = mission_cfg.get("search_area", {})
        container.safety = SafetyMonitor.from_config(
            geofence_radius_m=safety_cfg.get("geofence_radius_m", 500),
            max_altitude_m=safety_cfg.get("max_altitude_m", 120),
            min_battery_pct=safety_cfg.get("min_battery_percent", 20),
            critical_battery_pct=safety_cfg.get(
                "critical_battery_percent", 10,
            ),
            home_lat=search_area.get("center_lat", 47.397742),
            home_lon=search_area.get("center_lon", 8.545594),
        )

        # --- State Machine ---
        container.state_machine = MissionStateMachine(
            connector=container.connector,
            flight=container.flight,
            detector=container.detector,
            tracker=container.tracker,
            geotagger=container.geotagger,
            camera=container.camera,
            safety=container.safety,
            config=mission_cfg,
            event_bus=container.event_bus,
        )

    @staticmethod
    async def shutdown(container) -> None:
        """Graceful shutdown of all subsystems."""
        if container.video_server:
            container.video_server.stop()
        if container.camera:
            container.camera.release()
        if container.telemetry_collector:
            await container.telemetry_collector.stop()
        if container.connector:
            await container.connector.disconnect()
        if container.event_bus:
            container.event_bus.clear()
