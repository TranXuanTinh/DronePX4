"""
Battery failsafe tests — FAA compliance.

Validates battery threshold enforcement: low-battery RTL and
critical-battery emergency landing.

DO-178C Traceability: REQ-BAT-001 through REQ-BAT-005
"""
import pytest

from src.core.types import SafetyAction
from src.mission.safety import BatteryRule, SafetyMonitor


@pytest.mark.failsafe
class TestBatteryThresholds:
    """Test battery level threshold enforcement."""

    def test_healthy_battery_is_safe(self, make_telemetry):
        """REQ-BAT-001: Battery at 80% → NONE."""
        rule = BatteryRule(min_pct=20.0, critical_pct=10.0)
        telem = make_telemetry(battery=80.0)
        assert rule.evaluate(telem) == SafetyAction.NONE

    def test_low_battery_triggers_rtl(self, make_telemetry):
        """REQ-BAT-002: Battery at 15% (< 20%) → RTL_NOW."""
        rule = BatteryRule(min_pct=20.0, critical_pct=10.0)
        telem = make_telemetry(battery=15.0)
        assert rule.evaluate(telem) == SafetyAction.RTL_NOW

    def test_critical_battery_triggers_emergency_land(self, make_telemetry):
        """REQ-BAT-003: Battery at 5% (< 10%) → EMERGENCY_LAND."""
        rule = BatteryRule(min_pct=20.0, critical_pct=10.0)
        telem = make_telemetry(battery=5.0)
        assert rule.evaluate(telem) == SafetyAction.EMERGENCY_LAND

    def test_zero_battery_is_data_unavailable(self, make_telemetry):
        """REQ-BAT-004: Battery at 0% → NONE (data not available)."""
        rule = BatteryRule(min_pct=20.0, critical_pct=10.0)
        telem = make_telemetry(battery=0.0)
        assert rule.evaluate(telem) == SafetyAction.NONE

    @pytest.mark.parametrize("battery_pct,expected_action", [
        (100.0, SafetyAction.NONE),
        (50.0, SafetyAction.NONE),
        (25.0, SafetyAction.NONE),
        (20.0, SafetyAction.NONE),
        (19.9, SafetyAction.RTL_NOW),
        (15.0, SafetyAction.RTL_NOW),
        (10.0, SafetyAction.RTL_NOW),
        (9.9, SafetyAction.EMERGENCY_LAND),
        (5.0, SafetyAction.EMERGENCY_LAND),
        (1.0, SafetyAction.EMERGENCY_LAND),
        (0.0, SafetyAction.NONE),  # Data not available
    ])
    def test_battery_thresholds_parametrized(
        self, make_telemetry, battery_pct, expected_action
    ):
        """REQ-BAT-005: Comprehensive battery threshold sweep."""
        rule = BatteryRule(min_pct=20.0, critical_pct=10.0)
        telem = make_telemetry(battery=battery_pct)
        assert rule.evaluate(telem) == expected_action


@pytest.mark.failsafe
class TestBatteryInSafetyMonitor:
    """Test battery rules within the composite SafetyMonitor."""

    def test_low_battery_rtl_with_full_monitor(
        self, make_telemetry, safety_monitor
    ):
        """REQ-BAT-002: SafetyMonitor triggers RTL on low battery."""
        telem = make_telemetry(battery=15.0)
        result = safety_monitor.check(telem)
        assert result >= SafetyAction.RTL_NOW

    def test_critical_battery_emergency_with_full_monitor(
        self, make_telemetry, safety_monitor
    ):
        """REQ-BAT-003: SafetyMonitor triggers EMERGENCY_LAND on critical."""
        telem = make_telemetry(battery=5.0)
        result = safety_monitor.check(telem)
        assert result == SafetyAction.EMERGENCY_LAND

    def test_custom_battery_thresholds(self, make_telemetry, custom_safety_monitor):
        """REQ-BAT-005: Custom threshold (50% min) triggers at 45%."""
        monitor = custom_safety_monitor(min_battery_pct=50.0, critical_battery_pct=25.0)
        telem = make_telemetry(battery=45.0)
        result = monitor.check(telem)
        assert result >= SafetyAction.RTL_NOW
