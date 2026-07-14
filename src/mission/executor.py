"""
Mission Executor — state handler implementations.

Extracted from the monolithic MissionStateMachine for SRP compliance.
The state machine owns state/transitions; the executor owns behavior.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional

from src.core.interfaces import (
    DroneConnector, FlightController, ObjectDetector,
    ObjectTracker, Geotagger, CameraSource, SafetyChecker,
)
from src.core.types import (
    TelemetryFrame, Waypoint, GeotaggedDetection,
    Track, SafetyAction,
)
from src.core.geo import haversine_distance
from src.core.events import EventBus

logger = logging.getLogger(__name__)


class MissionExecutor:
    """Executes state handler logic for each mission state.

    Depends on abstract interfaces (DIP), not concrete classes.
    The MissionStateMachine delegates _do_xxx() calls here.
    """

    def __init__(
        self,
        connector: DroneConnector,
        flight: FlightController,
        detector: ObjectDetector,
        tracker: ObjectTracker,
        geotagger: Geotagger,
        camera: CameraSource,
        safety: SafetyChecker,
        config: dict,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.connector = connector
        self.flight = flight
        self.detector = detector
        self.tracker = tracker
        self.geotagger = geotagger
        self.camera = camera
        self.safety = safety
        self.config = config
        self.event_bus = event_bus

        # Shared mission data (owned by executor, read by state machine)
        self.waypoints: List[Waypoint] = []
        self.current_waypoint_idx: int = 0
        self.detections: List[GeotaggedDetection] = []
        self.current_tracks: List[Track] = []
        self.pending_detection: Optional[GeotaggedDetection] = None

    # ── State Handlers ───────────────────────────────────────

    async def do_preflight(self) -> str:
        """PREFLIGHT: Check vehicle readiness. Returns trigger name."""
        logger.info("Running preflight checks...")
        try:
            if not self.connector.is_connected:
                logger.error("Not connected to PX4 SITL")
                return "checks_fail"

            # Active gRPC health check — verify the channel is alive
            if hasattr(self.connector, 'is_healthy'):
                healthy = await self.connector.is_healthy()
                if not healthy:
                    logger.error(
                        "MAVSDK gRPC channel is not healthy. "
                        "Attempting reconnection..."
                    )
                    if hasattr(self.connector, 'reconnect'):
                        reconnected = await self.connector.reconnect()
                        if not reconnected:
                            logger.error("Reconnection failed")
                            return "checks_fail"
                        # Refresh flight command references
                        if hasattr(self.flight, '_refresh_drone_ref'):
                            self.flight._refresh_drone_ref()
                        logger.info("Reconnected successfully")
                    else:
                        return "checks_fail"

            # Wait up to 15 seconds for a valid GPS fix
            gps_ok = False
            for _ in range(15):
                telem = self.connector.latest_telemetry
                if telem and telem.gps_fix_type >= 3:
                    gps_ok = True
                    break
                await asyncio.sleep(1.0)
                
            if not gps_ok:
                logger.error("No GPS fix (timed out waiting for 3D fix)")
                return "checks_fail"

            logger.info("Preflight checks passed")
            return "checks_pass"

        except Exception as e:
            logger.error(f"Preflight check failed: {e}")
            return "checks_fail"

    async def do_takeoff(self) -> str:
        """TAKEOFF: Arm and takeoff. Returns trigger name."""
        alt = self.config.get("takeoff_altitude_m", 15.0)
        logger.info(f"Taking off to {alt}m...")

        try:
            await self.flight.arm()
            await asyncio.sleep(1.0)
            await self.flight.takeoff(alt)
        except ConnectionError as e:
            logger.error(
                f"Takeoff failed — MAVSDK connection error: {e}. "
                "Aborting mission."
            )
            return "abort"
        except Exception as e:
            logger.error(
                f"Takeoff failed — unexpected error: {e}. "
                "Aborting mission."
            )
            return "abort"

        reached = await self.flight.wait_for_altitude(
            alt, tolerance_m=2.0, timeout_s=30.0,
        )
        if reached:
            logger.info("Takeoff altitude reached")
            return "altitude_reached"
        else:
            logger.error("Failed to reach takeoff altitude")
            return "abort"

    async def do_search(self) -> Optional[str]:
        """SEARCH: Navigate waypoints + perception. Returns trigger or None."""
        if self.current_waypoint_idx >= len(self.waypoints):
            logger.info("All waypoints visited, search complete")
            return "search_complete"

        # Safety check
        telem = self.connector.latest_telemetry
        if telem:
            action = self.safety.check(telem)
            if action == SafetyAction.RTL_NOW:
                logger.warning("Safety RTL triggered during search")
                return "safety_rtl"

        wp = self.waypoints[self.current_waypoint_idx]
        logger.debug(
            f"Navigating to waypoint {self.current_waypoint_idx}: {wp}"
        )

        await self.flight.goto(wp.latitude, wp.longitude, wp.altitude)

        # Run perception
        frame = self.camera.get_frame()
        if frame is not None:
            detections = self.detector.detect(frame)
            self.current_tracks = self.tracker.update(detections)

            confirmed = [t for t in self.current_tracks if t.is_confirmed]
            if confirmed and telem:
                geotagged = self.geotagger.tag_detections(
                    confirmed,
                    telem.position.latitude_deg,
                    telem.position.longitude_deg,
                    telem.position.relative_altitude_m,
                    telem.heading_deg,
                    time.time(),
                )
                if geotagged:
                    self.pending_detection = geotagged[0]
                    logger.info(
                        f"Object detected! "
                        f"{len(confirmed)} confirmed tracks"
                    )
                    return "object_detected"

        # Check waypoint arrival
        if telem:
            dist = self._distance_to_waypoint(telem, wp)
            if dist < 3.0:
                self.current_waypoint_idx += 1
                logger.info(
                    f"Waypoint reached. Progress: "
                    f"{self.current_waypoint_idx}/{len(self.waypoints)}"
                )

        return None  # Stay in SEARCH

    async def do_detect(self) -> str:
        """DETECT: Confirm detection over multiple frames."""
        confirm_frames = self.config.get("detection_confirm_frames", 5)
        confirm_count = 0

        logger.info(f"Confirming detection ({confirm_frames} frames)...")
        await self.flight.hold()

        for _ in range(confirm_frames * 2):
            frame = self.camera.get_frame()
            if frame is not None:
                detections = self.detector.detect(frame)
                tracks = self.tracker.update(detections)
                if any(t.is_confirmed for t in tracks):
                    confirm_count += 1
                if confirm_count >= confirm_frames:
                    logger.info("Detection confirmed!")
                    return "detection_confirmed"
            await asyncio.sleep(0.1)

        logger.info("Detection not confirmed — false positive")
        self.pending_detection = None
        return "false_positive"

    async def do_inspect(self) -> str:
        """INSPECT: Hover and capture frames."""
        logger.info("Inspecting detected object...")
        inspect_duration = 5.0
        start = time.time()

        while time.time() - start < inspect_duration:
            frame = self.camera.get_frame()
            if frame is not None:
                detections = self.detector.detect(frame)
                self.current_tracks = self.tracker.update(detections)
            await asyncio.sleep(0.2)

        logger.info("Inspection complete")
        return "inspection_done"

    async def do_log(self, on_detection=None) -> str:
        """LOG: Save geotagged detection, decide next action."""
        if self.pending_detection:
            self.detections.append(self.pending_detection)
            logger.info(
                f"Detection logged: {self.pending_detection.class_name} "
                f"at ({self.pending_detection.latitude_deg:.6f}, "
                f"{self.pending_detection.longitude_deg:.6f})"
            )
            if on_detection:
                await on_detection(self.pending_detection)
            self.pending_detection = None

        # Safety check
        telem = self.connector.latest_telemetry
        if telem:
            action = self.safety.check(telem)
            if action == SafetyAction.RTL_NOW:
                return "mission_complete"

        if self.current_waypoint_idx < len(self.waypoints):
            logger.info("Resuming search...")
            return "more_waypoints"
        else:
            logger.info("All waypoints visited, mission complete")
            return "mission_complete"

    async def do_rtl(self) -> str:
        """RTL: Return to launch and wait for landing."""
        logger.info("Returning to launch...")
        await self.flight.rtl()
        await self.flight.wait_for_landed(timeout_s=120.0)
        return "touchdown"

    async def do_landed(self) -> str:
        """LANDED: Disarm and finish."""
        logger.info("Vehicle landed, disarming...")
        await asyncio.sleep(2.0)
        try:
            await self.flight.disarm()
        except Exception:
            pass  # May already be disarmed
        return "disarmed"

    async def do_abort(self) -> str:
        """ABORT: Immediate RTL."""
        logger.warning("Executing abort — RTL")
        if self.flight.is_offboard_active:
            await self.flight.stop_offboard()
        return "abort_rtl"

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _distance_to_waypoint(
        telem: TelemetryFrame, wp: Waypoint,
    ) -> float:
        """Calculate horizontal distance to waypoint in meters."""
        return haversine_distance(
            telem.position.latitude_deg,
            telem.position.longitude_deg,
            wp.latitude,
            wp.longitude,
        )
