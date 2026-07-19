"""
State Machine — declarative mission state machine (SRP-compliant).

Only owns state definitions, transitions, and event triggers.
All state handler behavior is delegated to MissionExecutor.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Callable, List

from transitions import Machine

from src.core.interfaces import (
    DroneConnector, FlightController, ObjectDetector,
    ObjectTracker, Geotagger, CameraSource, SafetyChecker,
)
from src.core.types import (
    MissionState, Waypoint, GeotaggedDetection,
    StateChangeEvent,
)
from src.core.events import EventBus
from src.mission.executor import MissionExecutor

logger = logging.getLogger(__name__)


class MissionStateMachine:
    """Event-driven state machine for autonomous inspection missions.

    Thin orchestrator — delegates all behavior to MissionExecutor.
    Uses the `transitions` library for declarative state definition.

    Usage:
        sm = MissionStateMachine(connector, flight, detector, ...)
        await sm.run_mission(waypoints)
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
        {
            "trigger": "abort",
            "source": [
                "PREFLIGHT", "TAKEOFF", "SEARCH",
                "DETECT", "INSPECT", "LOG",
            ],
            "dest": "ABORT",
        },
        {"trigger": "abort_rtl", "source": "ABORT", "dest": "RTL"},
        # Safety RTL from any flying state
        {
            "trigger": "safety_rtl",
            "source": [
                "TAKEOFF", "SEARCH", "DETECT", "INSPECT", "LOG",
            ],
            "dest": "RTL",
        },
    ]

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
        # Legacy compat: accept 'bridge' and 'commands' kwargs
        bridge: Optional[DroneConnector] = None,
        commands: Optional[FlightController] = None,
    ) -> None:
        # Support legacy keyword arguments
        actual_connector = connector or bridge
        actual_flight = flight or commands

        self._executor = MissionExecutor(
            connector=actual_connector,
            flight=actual_flight,
            detector=detector,
            tracker=tracker,
            geotagger=geotagger,
            camera=camera,
            safety=safety,
            config=config,
            event_bus=event_bus,
        )
        self._event_bus = event_bus
        self._config = config

        # State machine
        self._machine = Machine(
            model=self,
            states=self.states,
            transitions=self.transitions,
            initial=MissionState.IDLE.value,
            send_event=True,
        )

        self._mission_start_time: float = 0.0
        self._mission_end_time: float = 0.0
        self._running = False

        # Legacy callbacks
        self._on_state_change: Optional[Callable] = None
        self._on_detection: Optional[Callable] = None

    # ── Properties ───────────────────────────────────────────

    @property
    def current_state(self) -> str:
        return self.state

    @property
    def detections(self) -> List[GeotaggedDetection]:
        return self._executor.detections.copy()

    @property
    def waypoints(self) -> List[Waypoint]:
        return self._executor.waypoints

    @property
    def current_waypoint_index(self) -> int:
        return self._executor.current_waypoint_idx

    @property
    def mission_elapsed_s(self) -> float:
        if self._mission_start_time == 0:
            return 0.0
        if self._running:
            return time.time() - self._mission_start_time
        if self._mission_end_time == 0.0:
            return 0.0
        return self._mission_end_time - self._mission_start_time

    # ── Callbacks (legacy API) ───────────────────────────────

    def set_callbacks(
        self,
        on_state_change: Optional[Callable] = None,
        on_detection: Optional[Callable] = None,
    ) -> None:
        self._on_state_change = on_state_change
        self._on_detection = on_detection

    # ── Mission Lifecycle ────────────────────────────────────

    async def run_mission(self, waypoints: List[Waypoint]) -> None:
        """Execute a full autonomous inspection mission."""
        self._executor.waypoints = waypoints
        self._executor.current_waypoint_idx = 0
        self._executor.detections = []
        self._mission_start_time = time.time()
        self._mission_end_time = 0.0
        self._running = True

        logger.info(f"Starting mission with {len(waypoints)} waypoints")

        self.start_mission()
        await self._notify_state_change()

        try:
            while self._running and self.state != MissionState.IDLE.value:
                await self._execute_current_state()
                await asyncio.sleep(0.05)  # 20 Hz loop
        except asyncio.CancelledError:
            logger.info("Mission cancelled")
            await self._executor.flight.rtl()
        except Exception as e:
            logger.error(f"Mission error: {e}", exc_info=True)
            await self._executor.flight.rtl()
        finally:
            self._running = False
            self._mission_end_time = time.time()

        logger.info(
            f"Mission complete. Duration: {self.mission_elapsed_s:.1f}s, "
            f"Detections: {len(self._executor.detections)}"
        )

    async def request_abort(self) -> None:
        """Request mission abort."""
        logger.warning("ABORT requested!")
        if self.state in (
            "PREFLIGHT", "TAKEOFF", "SEARCH",
            "DETECT", "INSPECT", "LOG",
        ):
            self.abort()
            await self._notify_state_change()

    # ── State Dispatch ───────────────────────────────────────

    async def _execute_current_state(self) -> None:
        """Dispatch to the appropriate executor method."""
        state = self.state
        trigger = None

        if state == MissionState.PREFLIGHT.value:
            trigger = await self._executor.do_preflight()
        elif state == MissionState.TAKEOFF.value:
            trigger = await self._executor.do_takeoff()
        elif state == MissionState.SEARCH.value:
            trigger = await self._executor.do_search()
        elif state == MissionState.DETECT.value:
            trigger = await self._executor.do_detect()
        elif state == MissionState.INSPECT.value:
            trigger = await self._executor.do_inspect()
        elif state == MissionState.LOG.value:
            trigger = await self._executor.do_log(self._on_detection)
        elif state == MissionState.RTL.value:
            trigger = await self._executor.do_rtl()
        elif state == MissionState.LANDED.value:
            trigger = await self._executor.do_landed()
            self._running = False
        elif state == MissionState.ABORT.value:
            trigger = await self._executor.do_abort()

        if trigger:
            # Fire the transition trigger dynamically
            trigger_fn = getattr(self, trigger, None)
            if trigger_fn:
                trigger_fn()
                await self._notify_state_change()

    # ── Notifications ────────────────────────────────────────

    async def _notify_state_change(self) -> None:
        logger.info(f"State → {self.state}")
        if self._on_state_change:
            await self._on_state_change(self.state)
        if self._event_bus:
            await self._event_bus.publish(
                StateChangeEvent(old_state="", new_state=self.state)
            )
