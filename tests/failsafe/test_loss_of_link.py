"""
Loss-of-link failsafe tests — FAA compliance.

Validates that the drone correctly executes RTH protocols
when communication with the GCS is severed.

DO-178C Traceability: REQ-LOL-001 through REQ-LOL-006
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.core.types import SafetyAction, MissionState
from src.mission.safety import ConnectionRule, SafetyMonitor
from src.mission.executor import MissionExecutor


@pytest.mark.failsafe
class TestLossOfLinkDetection:
    """Test connection loss detection and response."""

    def test_connection_loss_triggers_rtl(self, make_telemetry):
        """REQ-LOL-001: is_connected=False → RTL_NOW."""
        rule = ConnectionRule()
        telem = make_telemetry(connected=False)
        assert rule.evaluate(telem) == SafetyAction.RTL_NOW

    def test_connection_ok_is_safe(self, make_telemetry):
        """REQ-LOL-001: is_connected=True → NONE."""
        rule = ConnectionRule()
        telem = make_telemetry(connected=True)
        assert rule.evaluate(telem) == SafetyAction.NONE

    def test_connection_loss_in_safety_monitor(
        self, make_telemetry, safety_monitor
    ):
        """REQ-LOL-002: SafetyMonitor catches connection loss."""
        telem = make_telemetry(connected=False)
        result = safety_monitor.check(telem)
        assert result >= SafetyAction.RTL_NOW

    @pytest.mark.asyncio
    async def test_connection_loss_during_search_triggers_safety_rtl(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config, make_telemetry, sample_waypoints,
    ):
        """REQ-LOL-003: Connection loss in SEARCH → safety_rtl trigger."""
        mock_safety.check = MagicMock(return_value=SafetyAction.RTL_NOW)
        mock_connector.latest_telemetry = make_telemetry(connected=False)

        executor = MissionExecutor(
            connector=mock_connector, flight=mock_flight,
            detector=mock_detector, tracker=mock_tracker,
            geotagger=mock_geotagger, camera=mock_camera,
            safety=mock_safety, config=default_config,
        )
        executor.waypoints = sample_waypoints
        executor.current_waypoint_idx = 0

        result = await executor.do_search()
        assert result == "safety_rtl"

    @pytest.mark.asyncio
    async def test_connection_loss_during_preflight_fails(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-LOL-004: Connection lost during PREFLIGHT → checks_fail."""
        mock_connector.is_connected = False

        executor = MissionExecutor(
            connector=mock_connector, flight=mock_flight,
            detector=mock_detector, tracker=mock_tracker,
            geotagger=mock_geotagger, camera=mock_camera,
            safety=mock_safety, config=default_config,
        )

        result = await executor.do_preflight()
        assert result == "checks_fail"


@pytest.mark.failsafe
class TestLossOfLinkTiming:
    """Test response time for loss-of-link scenarios."""

    def test_connection_rule_evaluates_instantly(self, make_telemetry):
        """REQ-LOL-006: Connection check completes in < 1ms."""
        import time
        rule = ConnectionRule()
        telem = make_telemetry(connected=False)

        start = time.perf_counter()
        result = rule.evaluate(telem)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result == SafetyAction.RTL_NOW
        assert elapsed_ms < 1.0, f"Connection check took {elapsed_ms:.2f}ms"

    def test_safety_monitor_evaluates_all_rules_quickly(
        self, make_telemetry, safety_monitor
    ):
        """REQ-LOL-006: Full safety check completes in < 5ms."""
        import time
        telem = make_telemetry(connected=False)

        start = time.perf_counter()
        result = safety_monitor.check(telem)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result >= SafetyAction.RTL_NOW
        assert elapsed_ms < 5.0, f"Safety check took {elapsed_ms:.2f}ms"
