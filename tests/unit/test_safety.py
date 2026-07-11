"""
Unit tests for SafetyMonitor — Chain of Responsibility pattern.

Tests individual SafetyRule implementations and the composite
SafetyMonitor.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.types import (
    SafetyAction, TelemetryFrame, Position, Attitude,
)
from src.core.geo import haversine_distance
from src.mission.safety import (
    SafetyMonitor,
    BatteryRule,
    GeofenceRule,
    AltitudeRule,
    ConnectionRule,
)


def _make_telemetry(
    lat=47.397742, lon=8.545594, alt=15.0,
    battery=80.0, connected=True,
):
    """Create a TelemetryFrame for testing."""
    return TelemetryFrame(
        timestamp=0.0,
        position=Position(lat, lon, 0, alt),
        attitude=Attitude(0, 0, 0),
        heading_deg=0.0,
        groundspeed_ms=0.0,
        battery_percent=battery,
        battery_voltage=16.0,
        flight_mode="OFFBOARD",
        armed=True,
        is_connected=connected,
        gps_num_satellites=12,
        gps_fix_type=3,
    )


class TestSafetyMonitor:
    """Test the composite SafetyMonitor (Chain of Responsibility)."""

    def test_all_ok_returns_none(self, monitor=None):
        m = monitor or SafetyMonitor.from_config()
        telem = _make_telemetry()
        assert m.check(telem) == SafetyAction.NONE

    def test_low_battery_warns(self, monitor=None):
        m = monitor or SafetyMonitor.from_config()
        telem = _make_telemetry(battery=15.0)
        assert m.check(telem) == SafetyAction.RTL_NOW

    def test_critical_battery_emergency(self, monitor=None):
        m = monitor or SafetyMonitor.from_config()
        telem = _make_telemetry(battery=5.0)
        assert m.check(telem) == SafetyAction.EMERGENCY_LAND

    def test_zero_battery_ignored(self, monitor=None):
        m = monitor or SafetyMonitor.from_config()
        telem = _make_telemetry(battery=0.0)
        # Zero battery = data not available, should not trigger action
        result = m.check(telem)
        assert result != SafetyAction.EMERGENCY_LAND

    def test_geofence_breach_rtl(self, monitor=None):
        m = monitor or SafetyMonitor.from_config()
        telem = _make_telemetry(lat=47.41, lon=8.56)
        assert m.check(telem) == SafetyAction.RTL_NOW

    def test_within_geofence_ok(self, monitor=None):
        m = monitor or SafetyMonitor.from_config()
        telem = _make_telemetry(lat=47.397742, lon=8.545594)
        assert m.check(telem) == SafetyAction.NONE

    def test_altitude_exceeded_rtl(self, monitor=None):
        m = monitor or SafetyMonitor.from_config()
        telem = _make_telemetry(alt=150.0)
        assert m.check(telem) == SafetyAction.RTL_NOW

    def test_altitude_near_limit_warns(self, monitor=None):
        m = monitor or SafetyMonitor.from_config()
        telem = _make_telemetry(alt=115.0)
        assert m.check(telem) == SafetyAction.WARN

    def test_connection_lost_rtl(self, monitor=None):
        m = monitor or SafetyMonitor.from_config()
        telem = _make_telemetry(connected=False)
        assert m.check(telem) == SafetyAction.RTL_NOW


class TestIndividualRules:
    """Test each SafetyRule in isolation (Chain of Responsibility)."""

    def test_battery_rule_ok(self):
        rule = BatteryRule(min_pct=20, critical_pct=10)
        telem = _make_telemetry(battery=80)
        assert rule.evaluate(telem) == SafetyAction.NONE

    def test_battery_rule_critical(self):
        rule = BatteryRule(min_pct=20, critical_pct=10)
        telem = _make_telemetry(battery=5)
        assert rule.evaluate(telem) == SafetyAction.EMERGENCY_LAND

    def test_geofence_rule_ok(self):
        rule = GeofenceRule(47.397742, 8.545594, 500)
        telem = _make_telemetry()
        assert rule.evaluate(telem) == SafetyAction.NONE

    def test_altitude_rule_exceeded(self):
        rule = AltitudeRule(max_altitude_m=120)
        telem = _make_telemetry(alt=150)
        assert rule.evaluate(telem) == SafetyAction.RTL_NOW

    def test_connection_rule_ok(self):
        rule = ConnectionRule()
        telem = _make_telemetry(connected=True)
        assert rule.evaluate(telem) == SafetyAction.NONE

    def test_connection_rule_lost(self):
        rule = ConnectionRule()
        telem = _make_telemetry(connected=False)
        assert rule.evaluate(telem) == SafetyAction.RTL_NOW

    def test_add_custom_rule(self):
        """Verify OCP — can add rules without changing SafetyMonitor."""
        monitor = SafetyMonitor()
        monitor.add_rule(BatteryRule(min_pct=50, critical_pct=25))
        telem = _make_telemetry(battery=30)
        assert monitor.check(telem) == SafetyAction.RTL_NOW


class TestHaversineDistance:
    """Test GPS distance from core.geo."""

    def test_same_point_zero_distance(self):
        d = haversine_distance(47.3977, 8.5456, 47.3977, 8.5456)
        assert d < 0.01

    def test_known_distance(self):
        d = haversine_distance(47.3977, 8.5456, 47.4077, 8.5456)
        assert 1000 < d < 1200

    def test_short_distance(self):
        d = haversine_distance(47.3977, 8.5456, 47.3978, 8.5456)
        assert 5 < d < 20
