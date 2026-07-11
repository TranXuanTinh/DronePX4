#!/usr/bin/env python3
"""
run_mission.py — Main entry point for autonomous inspection mission.

Uses AppFactory for subsystem construction (eliminates duplicated wiring).
Connects to PX4 SITL, initializes all subsystems, and runs the
mission state machine.

Usage:
    # 1. Start PX4 SITL first:  ./scripts/launch_sitl.sh
    # 2. Run mission:           python scripts/run_mission.py
"""
from __future__ import annotations

import asyncio
import argparse
import logging
import signal
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger import setup_logging
from src.utils.config_loader import load_config
from src.core.events import EventBus
from src.bridge.mavlink_bridge import MAVLinkBridge
from src.bridge.commands import FlightCommands
from src.perception.camera import CameraFactory
from src.perception.detector import YOLODetector
from src.perception.tracker import ByteTrackWrapper
from src.perception.geotagging import GPSGeotagger
from src.mission.state_machine import MissionStateMachine
from src.mission.safety import SafetyMonitor
from src.mission.waypoint_planner import PatternRegistry

logger = logging.getLogger(__name__)


async def main(config_path: str = None):
    """Main mission execution."""

    # Load config
    config = load_config(config_path)
    setup_logging(
        level=config.get("logging", {}).get("level", "INFO"),
        log_dir=config.get("logging", {}).get("log_dir", "data/logs"),
    )

    logger.info("=" * 60)
    logger.info("  Drone Inspector — Autonomous Mission (SITL)")
    logger.info("=" * 60)

    event_bus = EventBus()

    # === Initialize subsystems ===

    # MAVLink bridge (with context manager)
    bridge = MAVLinkBridge(
        connection_string=config.get("connection", {}).get("mavsdk_address"),
    )
    await bridge.connect()
    await bridge.wait_for_ready()

    # Start telemetry
    await bridge.start_telemetry_stream(
        rate_hz=config.get("dashboard", {}).get("telemetry_rate_hz", 10.0),
    )

    # Flight commands
    commands = FlightCommands(bridge)

    # Camera (factory creates correct implementation)
    cam_config = config.get("camera", {})
    camera = CameraFactory.create(
        source=cam_config.get("source", "gazebo"),
        width=cam_config.get("width", 640),
        height=cam_config.get("height", 480),
    )
    camera.open()

    # Perception
    perc_config = config.get("perception", {})
    detector = YOLODetector(
        model_path=perc_config.get("model", "yolov8s.pt"),
        device=perc_config.get("device", "cpu"),
        conf_thresh=perc_config.get("confidence_threshold", 0.45),
        target_classes=perc_config.get("classes"),
    )
    detector.load()

    tracker_config = perc_config.get("tracker", {})
    tracker = ByteTrackWrapper(
        track_thresh=tracker_config.get("track_thresh", 0.5),
        match_thresh=tracker_config.get("match_thresh", 0.8),
        track_buffer=tracker_config.get("track_buffer", 30),
        frame_rate=tracker_config.get("frame_rate", 10),
    )

    geotagger = GPSGeotagger(
        camera_hfov_deg=cam_config.get("hfov_deg", 60),
        image_width=cam_config.get("width", 640),
        image_height=cam_config.get("height", 480),
    )

    # Safety (Chain of Responsibility)
    safety_config = config.get("safety", {})
    mission_config = config.get("mission", {})
    search_area = mission_config.get("search_area", {})

    safety = SafetyMonitor.from_config(
        geofence_radius_m=safety_config.get("geofence_radius_m", 500),
        max_altitude_m=safety_config.get("max_altitude_m", 120),
        min_battery_pct=safety_config.get("min_battery_percent", 20),
        critical_battery_pct=safety_config.get("critical_battery_percent", 10),
        home_lat=search_area.get("center_lat", 47.397742),
        home_lon=search_area.get("center_lon", 8.545594),
    )

    # === Generate waypoints (Strategy pattern) ===
    pattern = mission_config.get("search_pattern", "lawnmower")

    pattern_config = {
        "center_lat": search_area.get("center_lat", 47.397742),
        "center_lon": search_area.get("center_lon", 8.545594),
        "width_m": search_area.get("width_m", 200),
        "height_m": search_area.get("height_m", 150),
        "spacing_m": search_area.get("spacing_m", 30),
        "altitude_m": mission_config.get("search_altitude_m", 20.0),
        "initial_radius_m": 20,
        "expansion_m": 15,
        "max_radius_m": 100,
    }

    try:
        waypoints = PatternRegistry.generate(pattern, pattern_config)
    except ValueError:
        logger.warning(f"Unknown pattern '{pattern}', using lawnmower")
        waypoints = PatternRegistry.generate("lawnmower", pattern_config)

    logger.info(f"Generated {len(waypoints)} waypoints ({pattern} pattern)")

    # === Create and run state machine ===
    state_machine = MissionStateMachine(
        connector=bridge,
        flight=commands,
        detector=detector,
        tracker=tracker,
        geotagger=geotagger,
        camera=camera,
        safety=safety,
        config=mission_config,
        event_bus=event_bus,
    )

    # Handle Ctrl+C gracefully
    abort_event = asyncio.Event()

    def signal_handler():
        logger.warning("Ctrl+C received — aborting mission")
        abort_event.set()
        asyncio.ensure_future(state_machine.request_abort())

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, signal_handler)

    # Run mission
    logger.info("Starting autonomous mission...")
    await state_machine.run_mission(waypoints)

    # === Cleanup ===
    camera.release()
    await bridge.disconnect()

    # Report
    detections = state_machine.detections
    logger.info("=" * 60)
    logger.info("  Mission Complete!")
    logger.info(f"  Duration:   {state_machine.mission_elapsed_s:.1f}s")
    logger.info(f"  Waypoints:  {len(waypoints)}")
    logger.info(f"  Detections: {len(detections)}")
    logger.info("=" * 60)

    if detections:
        logger.info("Detection summary:")
        for d in detections:
            logger.info(
                f"  [{d.class_name}] conf={d.confidence:.2f} "
                f"GPS=({d.latitude_deg:.6f}, {d.longitude_deg:.6f})"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run autonomous inspection mission in PX4 SITL",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to config YAML (default: config/vehicle/sim_config.yaml)",
    )
    args = parser.parse_args()

    asyncio.run(main(config_path=args.config))
