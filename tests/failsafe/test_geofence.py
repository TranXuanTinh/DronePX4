"""
Geofence failsafe tests — ISO 21384 / FAA compliance.

Validates that the drone automatically triggers RTL when
approaching or breaching geofence boundaries.

DO-178C Traceability: REQ-GEO-001 through REQ-GEO-006
"""
import pytest

from src.core.types import SafetyAction
from src.core.geo import haversine_distance, offset_gps
from src.mission.safety import GeofenceRule, SafetyMonitor


@pytest.mark.failsafe
class TestGeofenceDetection:
    """Test geofence boundary detection at various distances."""

    def test_well_within_geofence_is_safe(self, make_telemetry, safety_monitor):
        """REQ-GEO-001: Drone at home position → NONE."""
        telem = make_telemetry(lat=47.397742, lon=8.545594)
        assert safety_monitor.check(telem) == SafetyAction.NONE

    def test_90_percent_of_radius_warns(self, make_telemetry):
        """REQ-GEO-002: Drone at >90% of geofence → WARN."""
        rule = GeofenceRule(47.397742, 8.545594, radius_m=500.0)
        # Move drone to ~460m from home (92% of 500m, > 90%)
        lat, lon = offset_gps(47.397742, 8.545594, 460.0, 0.0)
        telem = make_telemetry(lat=lat, lon=lon)
        result = rule.evaluate(telem)
        assert result == SafetyAction.WARN

    def test_beyond_geofence_triggers_rtl(self, make_telemetry):
        """REQ-GEO-003: Drone beyond geofence radius → RTL_NOW."""
        rule = GeofenceRule(47.397742, 8.545594, radius_m=500.0)
        # Move drone to ~600m from home (beyond 500m limit)
        lat, lon = offset_gps(47.397742, 8.545594, 600.0, 0.0)
        telem = make_telemetry(lat=lat, lon=lon)
        result = rule.evaluate(telem)
        assert result == SafetyAction.RTL_NOW

    @pytest.mark.parametrize("radius_m", [50, 100, 500, 1000])
    def test_custom_geofence_radii(self, make_telemetry, radius_m):
        """REQ-GEO-004: Various geofence sizes enforce correctly."""
        rule = GeofenceRule(47.397742, 8.545594, radius_m=radius_m)

        # Just inside — should be safe
        lat_in, lon_in = offset_gps(47.397742, 8.545594, radius_m * 0.8, 0.0)
        telem_in = make_telemetry(lat=lat_in, lon=lon_in)
        assert rule.evaluate(telem_in) == SafetyAction.NONE

        # Beyond — should trigger RTL
        lat_out, lon_out = offset_gps(47.397742, 8.545594, radius_m * 1.1, 0.0)
        telem_out = make_telemetry(lat=lat_out, lon=lon_out)
        assert rule.evaluate(telem_out) == SafetyAction.RTL_NOW

    def test_geofence_on_exact_boundary(self, make_telemetry):
        """REQ-GEO-005: Drone exactly on boundary → RTL_NOW."""
        radius_m = 500.0
        rule = GeofenceRule(47.397742, 8.545594, radius_m=radius_m)
        # Move to slightly beyond the radius
        lat, lon = offset_gps(47.397742, 8.545594, radius_m + 1.0, 0.0)
        telem = make_telemetry(lat=lat, lon=lon)
        assert rule.evaluate(telem) == SafetyAction.RTL_NOW

    def test_geofence_in_all_cardinal_directions(self, make_telemetry):
        """REQ-GEO-006: Geofence enforced in N, S, E, W directions."""
        radius_m = 500.0
        rule = GeofenceRule(47.397742, 8.545594, radius_m=radius_m)

        directions = [
            (600.0, 0.0),    # North
            (-600.0, 0.0),   # South
            (0.0, 600.0),    # East
            (0.0, -600.0),   # West
        ]

        for north_offset, east_offset in directions:
            lat, lon = offset_gps(47.397742, 8.545594, north_offset, east_offset)
            telem = make_telemetry(lat=lat, lon=lon)
            assert rule.evaluate(telem) == SafetyAction.RTL_NOW, (
                f"Geofence not enforced at offset ({north_offset}, {east_offset})"
            )


@pytest.mark.failsafe
class TestGeofenceMissionIntegration:
    """Test geofence interaction with mission state machine."""

    def test_safety_monitor_geofence_with_full_rule_set(
        self, make_telemetry, safety_monitor
    ):
        """REQ-GEO-003: Full SafetyMonitor catches geofence breach."""
        # Far from home — geofence violation
        lat, lon = offset_gps(47.397742, 8.545594, 800.0, 0.0)
        telem = make_telemetry(lat=lat, lon=lon)
        result = safety_monitor.check(telem)
        assert result >= SafetyAction.RTL_NOW
