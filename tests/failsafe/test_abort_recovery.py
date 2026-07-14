"""
Abort recovery tests — validate abort from every flying state.

DO-178C Traceability: REQ-ABORT-001 through REQ-ABORT-008
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.core.types import MissionState, SafetyAction
from src.mission.state_machine import MissionStateMachine


@pytest.mark.failsafe
class TestAbortFromEveryState:
    """Test that abort transitions work from all flying states."""

    def _make_sm(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        return MissionStateMachine(
            connector=mock_connector, flight=mock_flight,
            detector=mock_detector, tracker=mock_tracker,
            geotagger=mock_geotagger, camera=mock_camera,
            safety=mock_safety, config=default_config,
        )

    def test_abort_from_preflight(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-ABORT-001: PREFLIGHT → ABORT."""
        sm = self._make_sm(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        sm.start_mission()
        assert sm.current_state == "PREFLIGHT"
        sm.abort()
        assert sm.current_state == "ABORT"

    def test_abort_from_takeoff(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-ABORT-002: TAKEOFF → ABORT."""
        sm = self._make_sm(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        sm.start_mission()
        sm.checks_pass()
        assert sm.current_state == "TAKEOFF"
        sm.abort()
        assert sm.current_state == "ABORT"

    def test_abort_from_search(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-ABORT-003: SEARCH → ABORT."""
        sm = self._make_sm(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        assert sm.current_state == "SEARCH"
        sm.abort()
        assert sm.current_state == "ABORT"

    def test_abort_from_detect(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-ABORT-004: DETECT → ABORT."""
        sm = self._make_sm(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.object_detected()
        assert sm.current_state == "DETECT"
        sm.abort()
        assert sm.current_state == "ABORT"

    def test_abort_from_inspect(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-ABORT-005: INSPECT → ABORT."""
        sm = self._make_sm(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.object_detected()
        sm.detection_confirmed()
        assert sm.current_state == "INSPECT"
        sm.abort()
        assert sm.current_state == "ABORT"

    def test_abort_from_log(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-ABORT-006: LOG → ABORT."""
        sm = self._make_sm(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()
        sm.object_detected()
        sm.detection_confirmed()
        sm.inspection_done()
        assert sm.current_state == "LOG"
        sm.abort()
        assert sm.current_state == "ABORT"


@pytest.mark.failsafe
class TestAbortRecovery:
    """Test full abort → RTL → LANDED → IDLE recovery."""

    def test_abort_rtl_to_landed_to_idle(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-ABORT-007: Full abort recovery: ABORT → RTL → LANDED → IDLE."""
        sm = MissionStateMachine(
            connector=mock_connector, flight=mock_flight,
            detector=mock_detector, tracker=mock_tracker,
            geotagger=mock_geotagger, camera=mock_camera,
            safety=mock_safety, config=default_config,
        )
        sm.start_mission()
        sm.checks_pass()
        sm.altitude_reached()

        # Abort
        sm.abort()
        assert sm.current_state == "ABORT"

        # Recovery
        sm.abort_rtl()
        assert sm.current_state == "RTL"

        sm.touchdown()
        assert sm.current_state == "LANDED"

        sm.disarmed()
        assert sm.current_state == "IDLE"

    def test_safety_rtl_from_all_flying_states(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-ABORT-008: safety_rtl works from all flying states."""
        flying_states = [
            "TAKEOFF", "SEARCH", "DETECT", "INSPECT", "LOG",
        ]

        for target_state in flying_states:
            sm = MissionStateMachine(
                connector=mock_connector, flight=mock_flight,
                detector=mock_detector, tracker=mock_tracker,
                geotagger=mock_geotagger, camera=mock_camera,
                safety=mock_safety, config=default_config,
            )

            # Navigate to target state
            sm.start_mission()
            sm.checks_pass()
            if target_state == "TAKEOFF":
                pass  # Already there
            elif target_state == "SEARCH":
                sm.altitude_reached()
            elif target_state == "DETECT":
                sm.altitude_reached()
                sm.object_detected()
            elif target_state == "INSPECT":
                sm.altitude_reached()
                sm.object_detected()
                sm.detection_confirmed()
            elif target_state == "LOG":
                sm.altitude_reached()
                sm.object_detected()
                sm.detection_confirmed()
                sm.inspection_done()

            assert sm.current_state == target_state
            sm.safety_rtl()
            assert sm.current_state == "RTL", (
                f"safety_rtl from {target_state} did not reach RTL"
            )
