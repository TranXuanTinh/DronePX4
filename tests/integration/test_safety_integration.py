"""
Integration tests: Safety → StateMachine interaction.

Validates that safety rule violations during active mission states
correctly trigger state machine transitions.

DO-178C Traceability: REQ-SAFE-INT-001 through REQ-SAFE-INT-003
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.core.types import SafetyAction
from src.mission.safety import SafetyMonitor, BatteryRule, GeofenceRule, AltitudeRule
from src.mission.state_machine import MissionStateMachine
from src.mission.executor import MissionExecutor


@pytest.mark.integration
class TestSafetyMissionIntegration:
    """Test safety rules driving state machine transitions."""

    def test_highest_priority_action_wins(self, make_telemetry):
        """REQ-SAFE-INT-001: Multiple violations → highest priority wins."""
        monitor = SafetyMonitor()
        monitor.add_rule(BatteryRule(min_pct=20, critical_pct=10))
        monitor.add_rule(AltitudeRule(max_altitude_m=120))

        # Both rules violated: battery critical (EMERGENCY_LAND) + altitude (RTL_NOW)
        telem = make_telemetry(battery=5.0, alt=150.0)
        result = monitor.check(telem)
        assert result == SafetyAction.EMERGENCY_LAND  # Higher priority

    def test_single_rule_violation_not_masked(self, make_telemetry):
        """REQ-SAFE-INT-002: One violation is not masked by OK rules."""
        monitor = SafetyMonitor()
        monitor.add_rule(BatteryRule(min_pct=20, critical_pct=10))
        monitor.add_rule(AltitudeRule(max_altitude_m=120))

        # Only altitude violated
        telem = make_telemetry(battery=80.0, alt=150.0)
        result = monitor.check(telem)
        assert result == SafetyAction.RTL_NOW

    def test_custom_rule_injection_at_runtime(self, make_telemetry):
        """REQ-SAFE-INT-003: Adding rules at runtime affects subsequent checks."""
        monitor = SafetyMonitor()
        telem = make_telemetry(battery=15.0)

        # No rules → safe
        assert monitor.check(telem) == SafetyAction.NONE

        # Add battery rule → triggers RTL
        monitor.add_rule(BatteryRule(min_pct=20, critical_pct=10))
        assert monitor.check(telem) == SafetyAction.RTL_NOW

    @pytest.mark.asyncio
    async def test_safety_rtl_during_search_state(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        default_config, make_telemetry, sample_waypoints,
    ):
        """REQ-SAFE-INT-001: Real SafetyMonitor triggers safety_rtl in SEARCH."""
        # Use real SafetyMonitor (not mock)
        real_safety = SafetyMonitor.from_config(
            min_battery_pct=20.0, critical_battery_pct=10.0,
        )

        # Simulate low battery during search
        mock_connector.latest_telemetry = make_telemetry(battery=15.0)

        executor = MissionExecutor(
            connector=mock_connector, flight=mock_flight,
            detector=mock_detector, tracker=mock_tracker,
            geotagger=mock_geotagger, camera=mock_camera,
            safety=real_safety, config=default_config,
        )
        executor.waypoints = sample_waypoints
        executor.current_waypoint_idx = 0

        result = await executor.do_search()
        assert result == "safety_rtl"
