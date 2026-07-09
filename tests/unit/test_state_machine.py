"""Unit tests for the mission state machine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.mission.state_machine import MissionStateMachine, MissionState
from src.mission.waypoint_planner import Waypoint


@pytest.fixture
def mock_deps():
    """Create mock dependencies for the state machine."""
    bridge = MagicMock()
    bridge.is_connected = True
    bridge.latest_telemetry = MagicMock(
        gps_fix_type=3,
        battery_percent=80.0,
        position=MagicMock(
            latitude_deg=47.397742,
            longitude_deg=8.545594,
            relative_altitude_m=0.0,
        ),
        heading_deg=0.0,
        groundspeed_ms=0.0,
        flight_mode="MANUAL",
        armed=False,
        is_connected=True,
        gps_num_satellites=12,
    )

    commands = MagicMock()
    commands.arm = AsyncMock()
    commands.takeoff = AsyncMock()
    commands.rtl = AsyncMock()
    commands.land = AsyncMock()
    commands.hold = AsyncMock()
    commands.disarm = AsyncMock()
    commands.goto = AsyncMock()
    commands.wait_for_altitude = AsyncMock(return_value=True)
    commands.wait_for_landed = AsyncMock(return_value=True)
    commands.is_offboard_active = False
    commands.stop_offboard = AsyncMock()

    detector = MagicMock()
    detector.detect = MagicMock(return_value=[])

    tracker = MagicMock()
    tracker.update = MagicMock(return_value=[])

    geotagger = MagicMock()
    camera = MagicMock()
    camera.get_frame = MagicMock(return_value=None)

    safety = MagicMock()
    safety.check = MagicMock(return_value=0)  # SafetyAction.NONE

    config = {
        "takeoff_altitude_m": 15.0,
        "search_altitude_m": 20.0,
        "detection_confirm_frames": 3,
    }

    return bridge, commands, detector, tracker, geotagger, camera, safety, config


def create_sm(mock_deps):
    bridge, commands, detector, tracker, geotagger, camera, safety, config = mock_deps
    return MissionStateMachine(
        bridge=bridge, commands=commands,
        detector=detector, tracker=tracker,
        geotagger=geotagger, camera=camera,
        safety=safety, config=config,
    )


class TestStateMachineTransitions:
    """Test state machine transitions."""

    def test_initial_state_is_idle(self, mock_deps):
        sm = create_sm(mock_deps)
        assert sm.current_state == "IDLE"

    def test_start_mission_transitions_to_preflight(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        assert sm.current_state == "PREFLIGHT"

    def test_preflight_pass_transitions_to_takeoff(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        assert sm.current_state == "TAKEOFF"

    def test_preflight_fail_returns_to_idle(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_fail()
        assert sm.current_state == "IDLE"

    def test_takeoff_to_search(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        assert sm.current_state == "SEARCH"

    def test_search_to_detect(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.object_detected()
        assert sm.current_state == "DETECT"

    def test_detect_confirmed_to_inspect(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.object_detected()
        sm.detection_confirmed()
        assert sm.current_state == "INSPECT"

    def test_detect_false_positive_back_to_search(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.object_detected()
        sm.false_positive()
        assert sm.current_state == "SEARCH"

    def test_inspect_to_log(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.object_detected()
        sm.detection_confirmed()
        sm.inspection_done()
        assert sm.current_state == "LOG"

    def test_log_more_waypoints_to_search(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.object_detected()
        sm.detection_confirmed()
        sm.inspection_done()
        sm.more_waypoints()
        assert sm.current_state == "SEARCH"

    def test_log_mission_complete_to_rtl(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.object_detected()
        sm.detection_confirmed()
        sm.inspection_done()
        sm.mission_complete()
        assert sm.current_state == "RTL"

    def test_search_complete_to_rtl(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.search_complete()
        assert sm.current_state == "RTL"

    def test_rtl_to_landed(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.search_complete()
        sm.touchdown()
        assert sm.current_state == "LANDED"

    def test_landed_to_idle(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.search_complete()
        sm.touchdown()
        sm.disarmed()
        assert sm.current_state == "IDLE"

    def test_abort_from_search(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.abort()
        assert sm.current_state == "ABORT"

    def test_abort_rtl(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.abort()
        sm.abort_rtl()
        assert sm.current_state == "RTL"

    def test_safety_rtl_from_search(self, mock_deps):
        sm = create_sm(mock_deps)
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.safety_rtl()
        assert sm.current_state == "RTL"


class TestStateMachineProperties:
    """Test state machine property accessors."""

    def test_detections_empty_initially(self, mock_deps):
        sm = create_sm(mock_deps)
        assert sm.detections == []

    def test_waypoints_empty_initially(self, mock_deps):
        sm = create_sm(mock_deps)
        assert sm.waypoints == []

    def test_mission_elapsed_zero_initially(self, mock_deps):
        sm = create_sm(mock_deps)
        assert sm.mission_elapsed_s == 0.0
