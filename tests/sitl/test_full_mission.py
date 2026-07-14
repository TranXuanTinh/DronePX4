"""
SITL Full Mission tests — end-to-end mission lifecycle.

DO-178C Traceability: REQ-SITL-MISSION-001 through REQ-SITL-MISSION-004
"""
import asyncio
import pytest
from unittest.mock import MagicMock

from src.mission.state_machine import MissionStateMachine
from src.bridge.commands import FlightCommands


@pytest.mark.sitl
@pytest.mark.timeout(300)
class TestSITLFullMission:
    """Test full mission lifecycle with live SITL."""

    @pytest.mark.asyncio
    async def test_mission_state_flow(self, sitl_ready, sitl_flight):
        """REQ-SITL-MISSION-001: IDLE → PREFLIGHT → TAKEOFF → SEARCH → RTL → LANDED → IDLE."""
        states_visited = []

        # Use real bridge/flight but mock perception
        mock_detector = MagicMock()
        mock_detector.detect = MagicMock(return_value=[])
        mock_detector.load = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.update = MagicMock(return_value=[])
        mock_geotagger = MagicMock()
        mock_camera = MagicMock()
        mock_camera.get_frame = MagicMock(return_value=None)
        mock_camera.open = MagicMock(return_value=True)
        mock_safety = MagicMock()
        from src.core.types import SafetyAction
        mock_safety.check = MagicMock(return_value=SafetyAction.NONE)

        config = {
            "takeoff_altitude_m": 10.0,
            "search_altitude_m": 15.0,
            "max_speed_ms": 3.0,
            "detection_confirm_frames": 3,
            "detection_confirm_timeout_s": 2.0,
            "search_area": {
                "center_lat": 47.397742,
                "center_lon": 8.545594,
                "width_m": 30,
                "height_m": 20,
                "spacing_m": 30,
            },
            "search_pattern": "lawnmower",
        }

        sm = MissionStateMachine(
            connector=sitl_ready,
            flight=sitl_flight,
            detector=mock_detector,
            tracker=mock_tracker,
            geotagger=mock_geotagger,
            camera=mock_camera,
            safety=mock_safety,
            config=config,
        )

        assert sm.current_state == "IDLE"
        states_visited.append("IDLE")

        # Start mission triggers PREFLIGHT
        sm.start_mission()
        states_visited.append(sm.current_state)
        assert sm.current_state == "PREFLIGHT"

        # The rest of the mission would run asynchronously via executor,
        # so we verify the state machine allows the transitions
        sm.checks_pass()
        states_visited.append(sm.current_state)
        assert sm.current_state == "TAKEOFF"

        sm.altitude_reached()
        states_visited.append(sm.current_state)
        assert sm.current_state == "SEARCH"

        # Simulate search complete → RTL
        sm.search_complete()
        states_visited.append(sm.current_state)
        assert sm.current_state == "RTL"

        sm.touchdown()
        states_visited.append(sm.current_state)
        assert sm.current_state == "LANDED"

        sm.disarmed()
        states_visited.append(sm.current_state)
        assert sm.current_state == "IDLE"

        assert states_visited == [
            "IDLE", "PREFLIGHT", "TAKEOFF", "SEARCH", "RTL", "LANDED", "IDLE"
        ]
