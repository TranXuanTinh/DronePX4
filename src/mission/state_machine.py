"""
State Machine — Core autonomous inspection mission controller.

Manages state transitions: IDLE → PREFLIGHT → TAKEOFF → SEARCH →
DETECT → INSPECT → LOG → RTL → LANDED

Uses the `transitions` library for declarative state machine definition.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Optional, Callable, Awaitable

from transitions import Machine

from src.bridge.mavlink_bridge import MAVLinkBridge, TelemetryFrame
from src.bridge.commands import FlightCommands
from src.perception.detector import YOLODetector
from src.perception.tracker import ByteTrackWrapper, Track
from src.perception.geotagging import GPSGeotagger, GeotaggedDetection
from src.perception.camera import GazeboCamera
from src.mission.safety import SafetyMonitor, SafetyAction
from src.mission.waypoint_planner import WaypointPlanner, Waypoint

logger = logging.getLogger(__name__)


class MissionState(str, Enum):
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    TAKEOFF = "TAKEOFF"
    SEARCH = "SEARCH"
    DETECT = "DETECT"
    INSPECT = "INSPECT"
    LOG = "LOG"
    RTL = "RTL"
    LANDED = "LANDED"
    ABORT = "ABORT"


class MissionStateMachine:
    """Event-driven state machine for autonomous inspection missions.

    Coordinates flight control, perception, and logging subsystems
    to execute a complete inspection mission in PX4 SITL.

    Usage:
        sm = MissionStateMachine(bridge, commands, detector, tracker, ...)
        await sm.start_mission(waypoints)
    """

    # State machine states
    states = [s.value for s in MissionState]

    # State machine transitions
    transitions = [
        {"trigger": "start_mission", "source": "IDLE", "dest": "PREFLIGHT"},
        {"trigger": "checks_pass", "source": "PREFLIGHT", "dest": "TAKEOFF"},
        {"trigger": "checks_fail", "source": "PREFLIGHT", "dest": "IDLE"},
        {"trigger": "altitude_reached", "source": "TAKEOFF", "dest": "SEARCH"},
        {"trigger": "object_detected", "source": "SEARCH", "dest": "DETECT"},
        {"trigger": "search_complete", "source": "SEARCH", "dest": "RTL"},
        {"trigger": "detection_confirmed", "source": "DETECT", "dest": "INSPECT"},
        {"trigger": "false_positive", "source": "DETECT", "dest": "SEARCH"},
        {"trigger": "inspection_done", "source": "INSPECT", "dest": "LOG"},
        {"trigger": "more_waypoints", "source": "LOG", "dest": "SEARCH"},
        {"trigger": "mission_complete", "source": "LOG", "dest": "RTL"},
        {"trigger": "touchdown", "source": "RTL", "dest": "LANDED"},
        {"trigger": "disarmed", "source": "LANDED", "dest": "IDLE"},
        # Abort from any active state
        {"trigger": "abort", "source": ["PREFLIGHT", "TAKEOFF", "SEARCH", "DETECT", "INSPECT", "LOG"], "dest": "ABORT"},
        {"trigger": "abort_rtl", "source": "ABORT", "dest": "RTL"},
        # Battery / safety RTL from any flying state
        {"trigger": "safety_rtl", "source": ["TAKEOFF", "SEARCH", "DETECT", "INSPECT", "LOG"], "dest": "RTL"},
    ]

    def __init__(
        self,
        bridge: MAVLinkBridge,
        commands: FlightCommands,
        detector: YOLODetector,
        tracker: ByteTrackWrapper,
        geotagger: GPSGeotagger,
        camera: GazeboCamera,
        safety: SafetyMonitor,
        config: dict,
    ):
        self._bridge = bridge
        self._commands = commands
        self._detector = detector
        self._tracker = tracker
        self._geotagger = geotagger
        self._camera = camera
        self._safety = safety
        self._config = config

        # State machine
        self._machine = Machine(
            model=self,
            states=self.states,
            transitions=self.transitions,
            initial=MissionState.IDLE.value,
            send_event=True,
        )

        # Mission data
        self._waypoints: list[Waypoint] = []
        self._current_waypoint_idx = 0
        self._detections: list[GeotaggedDetection] = []
        self._current_tracks: list[Track] = []
        self._pending_detection: Optional[GeotaggedDetection] = None
        self._mission_start_time: float = 0.0
        self._running = False

        # Callbacks for dashboard
        self._on_state_change: Optional[Callable] = None
        self._on_detection: Optional[Callable] = None
        self._on_telemetry: Optional[Callable] = None

    @property
    def current_state(self) -> str:
        return self.state

    @property
    def detections(self) -> list[GeotaggedDetection]:
        return self._detections.copy()

    @property
    def waypoints(self) -> list[Waypoint]:
        return self._waypoints

    @property
    def current_waypoint_index(self) -> int:
        return self._current_waypoint_idx

    @property
    def mission_elapsed_s(self) -> float:
        if self._mission_start_time == 0:
            return 0.0
        return time.time() - self._mission_start_time

    def set_callbacks(
        self,
        on_state_change: Optional[Callable] = None,
        on_detection: Optional[Callable] = None,
    ):
        """Register callbacks for state changes and detections."""
        self._on_state_change = on_state_change
        self._on_detection = on_detection

    async def run_mission(self, waypoints: list[Waypoint]) -> None:
        """Execute a full autonomous inspection mission.

        Args:
            waypoints: List of Waypoint objects defining the search pattern.
        """
        self._waypoints = waypoints
        self._current_waypoint_idx = 0
        self._detections = []
        self._mission_start_time = time.time()
        self._running = True

        logger.info(f"Starting mission with {len(waypoints)} waypoints")

        # Trigger state machine
        self.start_mission()
        await self._notify_state_change()

        try:
            while self._running and self.state != MissionState.IDLE.value:
                await self._execute_current_state()
                await asyncio.sleep(0.05)  # 20 Hz loop
        except asyncio.CancelledError:
            logger.info("Mission cancelled")
            await self._commands.rtl()
        except Exception as e:
            logger.error(f"Mission error: {e}", exc_info=True)
            await self._commands.rtl()
        finally:
            self._running = False

        logger.info(
            f"Mission complete. Duration: {self.mission_elapsed_s:.1f}s, "
            f"Detections: {len(self._detections)}"
        )

    async def request_abort(self) -> None:
        """Request mission abort (called from dashboard or keyboard)."""
        logger.warning("ABORT requested!")
        if self.state in ("PREFLIGHT", "TAKEOFF", "SEARCH", "DETECT", "INSPECT", "LOG"):
            self.abort()
            await self._notify_state_change()

    async def _execute_current_state(self) -> None:
        """Execute the action for the current state."""
        state = self.state

        if state == MissionState.PREFLIGHT.value:
            await self._do_preflight()
        elif state == MissionState.TAKEOFF.value:
            await self._do_takeoff()
        elif state == MissionState.SEARCH.value:
            await self._do_search()
        elif state == MissionState.DETECT.value:
            await self._do_detect()
        elif state == MissionState.INSPECT.value:
            await self._do_inspect()
        elif state == MissionState.LOG.value:
            await self._do_log()
        elif state == MissionState.RTL.value:
            await self._do_rtl()
        elif state == MissionState.LANDED.value:
            await self._do_landed()
        elif state == MissionState.ABORT.value:
            await self._do_abort()

    # === State Handlers ===

    async def _do_preflight(self):
        """PREFLIGHT: Check vehicle readiness."""
        logger.info("Running preflight checks...")

        try:
            # Check connection
            if not self._bridge.is_connected:
                logger.error("Not connected to PX4 SITL")
                self.checks_fail()
                return

            # Check GPS
            telem = self._bridge.latest_telemetry
            if telem and telem.gps_fix_type < 3:
                logger.error("No GPS fix")
                self.checks_fail()
                return

            logger.info("Preflight checks passed")
            self.checks_pass()
            await self._notify_state_change()

        except Exception as e:
            logger.error(f"Preflight check failed: {e}")
            self.checks_fail()
            await self._notify_state_change()

    async def _do_takeoff(self):
        """TAKEOFF: Arm and takeoff to mission altitude."""
        alt = self._config.get("takeoff_altitude_m", 15.0)
        logger.info(f"Taking off to {alt}m...")

        await self._commands.arm()
        await asyncio.sleep(1.0)
        await self._commands.takeoff(alt)

        # Wait for altitude
        reached = await self._commands.wait_for_altitude(alt, tolerance_m=2.0, timeout_s=30.0)

        if reached:
            logger.info("Takeoff altitude reached, transitioning to SEARCH")
            self.altitude_reached()
            await self._notify_state_change()
        else:
            logger.error("Failed to reach takeoff altitude")
            self.abort()
            await self._notify_state_change()

    async def _do_search(self):
        """SEARCH: Navigate waypoints while running perception."""
        if self._current_waypoint_idx >= len(self._waypoints):
            logger.info("All waypoints visited, search complete")
            self.search_complete()
            await self._notify_state_change()
            return

        # Check safety
        telem = self._bridge.latest_telemetry
        if telem:
            action = self._safety.check(telem)
            if action == SafetyAction.RTL_NOW:
                logger.warning("Safety RTL triggered during search")
                self.safety_rtl()
                await self._notify_state_change()
                return

        wp = self._waypoints[self._current_waypoint_idx]
        logger.debug(f"Navigating to waypoint {self._current_waypoint_idx}: {wp}")

        # Send goto command
        await self._commands.goto(wp.latitude, wp.longitude, wp.altitude)

        # Run perception while flying to waypoint
        frame = self._camera.get_frame()
        if frame is not None:
            detections = self._detector.detect(frame)
            self._current_tracks = self._tracker.update(detections)

            # Check for confirmed detections
            confirmed = [t for t in self._current_tracks if t.is_confirmed]
            if confirmed:
                logger.info(f"Object detected! {len(confirmed)} confirmed tracks")
                # Geotag the detection
                if telem:
                    geotagged = self._geotagger.tag_detections(
                        confirmed,
                        telem.position.latitude_deg,
                        telem.position.longitude_deg,
                        telem.position.relative_altitude_m,
                        telem.heading_deg,
                        time.time(),
                    )
                    if geotagged:
                        self._pending_detection = geotagged[0]
                        self.object_detected()
                        await self._notify_state_change()
                        return

        # Check if we've reached the current waypoint
        if telem:
            dist = self._distance_to_waypoint(telem, wp)
            if dist < 3.0:  # Within 3m of waypoint
                self._current_waypoint_idx += 1
                logger.info(
                    f"Waypoint reached. Progress: "
                    f"{self._current_waypoint_idx}/{len(self._waypoints)}"
                )

    async def _do_detect(self):
        """DETECT: Confirm detection over multiple frames."""
        confirm_frames = self._config.get("detection_confirm_frames", 5)
        confirm_count = 0

        logger.info(f"Confirming detection ({confirm_frames} frames)...")

        # Hover in place
        await self._commands.hold()

        for _ in range(confirm_frames * 2):  # Double the frames for margin
            frame = self._camera.get_frame()
            if frame is not None:
                detections = self._detector.detect(frame)
                tracks = self._tracker.update(detections)

                if any(t.is_confirmed for t in tracks):
                    confirm_count += 1

                if confirm_count >= confirm_frames:
                    logger.info("Detection confirmed!")
                    self.detection_confirmed()
                    await self._notify_state_change()
                    return

            await asyncio.sleep(0.1)

        logger.info("Detection not confirmed — false positive")
        self._pending_detection = None
        self.false_positive()
        await self._notify_state_change()

    async def _do_inspect(self):
        """INSPECT: Orbit around detected object for closer inspection."""
        logger.info("Inspecting detected object...")

        # For simulation, just hover for a few seconds and capture frames
        inspect_duration = 5.0
        start = time.time()

        while time.time() - start < inspect_duration:
            frame = self._camera.get_frame()
            if frame is not None:
                # Continue tracking during inspection
                detections = self._detector.detect(frame)
                self._current_tracks = self._tracker.update(detections)
            await asyncio.sleep(0.2)

        logger.info("Inspection complete")
        self.inspection_done()
        await self._notify_state_change()

    async def _do_log(self):
        """LOG: Save geotagged detection and decide next action."""
        if self._pending_detection:
            self._detections.append(self._pending_detection)
            logger.info(
                f"Detection logged: {self._pending_detection.class_name} "
                f"at ({self._pending_detection.latitude_deg:.6f}, "
                f"{self._pending_detection.longitude_deg:.6f})"
            )

            if self._on_detection:
                await self._on_detection(self._pending_detection)

            self._pending_detection = None

        # Decide: continue search or RTL
        telem = self._bridge.latest_telemetry
        if telem:
            action = self._safety.check(telem)
            if action == SafetyAction.RTL_NOW:
                self.mission_complete()
                await self._notify_state_change()
                return

        if self._current_waypoint_idx < len(self._waypoints):
            logger.info("Resuming search...")
            self.more_waypoints()
        else:
            logger.info("All waypoints visited, mission complete")
            self.mission_complete()

        await self._notify_state_change()

    async def _do_rtl(self):
        """RTL: Return to launch and wait for landing."""
        logger.info("Returning to launch...")
        await self._commands.rtl()

        # Wait for landing
        landed = await self._commands.wait_for_landed(timeout_s=120.0)
        if landed:
            self.touchdown()
        else:
            logger.warning("RTL landing timeout — forcing landed state")
            self.touchdown()

        await self._notify_state_change()

    async def _do_landed(self):
        """LANDED: Disarm and transition to IDLE."""
        logger.info("Vehicle landed, disarming...")
        await asyncio.sleep(2.0)

        try:
            await self._commands.disarm()
        except Exception:
            pass  # May already be disarmed

        self._running = False
        self.disarmed()
        await self._notify_state_change()

    async def _do_abort(self):
        """ABORT: Immediate RTL."""
        logger.warning("Executing abort — RTL")
        if self._commands.is_offboard_active:
            await self._commands.stop_offboard()
        self.abort_rtl()
        await self._notify_state_change()

    # === Helpers ===

    def _distance_to_waypoint(self, telem: TelemetryFrame, wp: Waypoint) -> float:
        """Calculate horizontal distance to waypoint in meters."""
        import math
        dlat = math.radians(wp.latitude - telem.position.latitude_deg)
        dlon = math.radians(wp.longitude - telem.position.longitude_deg)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(telem.position.latitude_deg))
            * math.cos(math.radians(wp.latitude))
            * math.sin(dlon / 2) ** 2
        )
        return 6_371_000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    async def _notify_state_change(self):
        """Notify callbacks of state change."""
        logger.info(f"State → {self.state}")
        if self._on_state_change:
            await self._on_state_change(self.state)
