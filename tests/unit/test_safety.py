"""Unit tests for the safety monitor.

Standalone — only depends on standard library.
Uses mock objects instead of importing TelemetryFrame (which requires mavsdk).
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mission.safety import SafetyMonitor, SafetyAction


def make_telemetry(battery=80, lat=47.397742, lon=8.545594, alt=20, connected=True):
    """Create a mock telemetry object matching TelemetryFrame interface."""
    telem = MagicMock()
    telem.battery_percent = battery
    telem.position = MagicMock()
    telem.position.latitude_deg = lat
    telem.position.longitude_deg = lon
    telem.position.relative_altitude_m = alt
    telem.is_connected = connected
    return telem


class TestSafetyMonitor:

    @pytest.fixture
    def monitor(self):
        return SafetyMonitor(
            geofence_radius_m=500,
            max_altitude_m=120,
            min_battery_pct=20,
            critical_battery_pct=10,
            home_lat=47.397742,
            home_lon=8.545594,
        )

    def test_all_ok_returns_none(self, monitor):
        assert monitor.check(make_telemetry(battery=80, alt=20)) == SafetyAction.NONE

    def test_low_battery_warns(self, monitor):
        assert monitor.check(make_telemetry(battery=15)) == SafetyAction.RTL_NOW

    def test_critical_battery_emergency(self, monitor):
        assert monitor.check(make_telemetry(battery=5)) == SafetyAction.EMERGENCY_LAND

    def test_altitude_exceeded_rtl(self, monitor):
        assert monitor.check(make_telemetry(alt=150)) == SafetyAction.RTL_NOW

    def test_altitude_near_limit_warns(self, monitor):
        assert monitor.check(make_telemetry(alt=115)) == SafetyAction.WARN

    def test_connection_lost_rtl(self, monitor):
        assert monitor.check(make_telemetry(connected=False)) == SafetyAction.RTL_NOW

    def test_geofence_breach_rtl(self, monitor):
        result = monitor.check(make_telemetry(lat=47.407, lon=8.555))
        assert result >= SafetyAction.RTL_NOW

    def test_within_geofence_ok(self, monitor):
        result = monitor.check(make_telemetry(lat=47.398, lon=8.546))
        assert result <= SafetyAction.WARN

    def test_zero_battery_ignored(self, monitor):
        assert monitor.check(make_telemetry(battery=0)) == SafetyAction.NONE


class TestHaversineDistance:

    def test_same_point_zero_distance(self):
        dist = SafetyMonitor._haversine_distance(47.0, 8.0, 47.0, 8.0)
        assert dist == pytest.approx(0, abs=0.01)

    def test_known_distance(self):
        dist = SafetyMonitor._haversine_distance(47.0, 8.0, 48.0, 8.0)
        assert 110_000 < dist < 112_000

    def test_short_distance(self):
        dist = SafetyMonitor._haversine_distance(
            47.397742, 8.545594, 47.398642, 8.545594,
        )
        assert 95 < dist < 105
