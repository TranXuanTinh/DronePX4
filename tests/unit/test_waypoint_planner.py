"""
Unit tests for WaypointPlanner — Strategy pattern.

Tests both the legacy WaypointPlanner API and the new
PatternRegistry / SearchPatternStrategy pattern.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.types import Waypoint
from src.core.geo import offset_gps
from src.mission.waypoint_planner import (
    WaypointPlanner,
    PatternRegistry,
    LawnmowerPattern,
    ExpandingSquarePattern,
    CustomWaypointsPattern,
)


# ── Legacy API Tests ─────────────────────────────────────────

class TestLawnmowerPattern:
    """Test lawnmower pattern generation."""

    def test_generates_waypoints(self):
        wps = WaypointPlanner.lawnmower(47.3977, 8.5456, 100, 100, 20, 15)
        assert len(wps) > 0
        assert all(isinstance(wp, Waypoint) for wp in wps)

    def test_altitude_set_correctly(self):
        wps = WaypointPlanner.lawnmower(47.3977, 8.5456, 100, 100, 20, 25.5)
        assert all(wp.altitude == 25.5 for wp in wps)

    def test_indices_sequential(self):
        wps = WaypointPlanner.lawnmower(47.3977, 8.5456, 100, 100, 20, 15)
        indices = [wp.index for wp in wps]
        assert indices == list(range(len(wps)))

    def test_waypoints_near_center(self):
        lat, lon = 47.3977, 8.5456
        wps = WaypointPlanner.lawnmower(lat, lon, 100, 100, 20, 15)
        for wp in wps:
            assert abs(wp.latitude - lat) < 0.01
            assert abs(wp.longitude - lon) < 0.01

    def test_wider_area_more_passes(self):
        wps_small = WaypointPlanner.lawnmower(47.3977, 8.5456, 50, 50, 20, 15)
        wps_large = WaypointPlanner.lawnmower(47.3977, 8.5456, 200, 200, 20, 15)
        assert len(wps_large) > len(wps_small)


class TestExpandingSquare:
    """Test expanding square pattern."""

    def test_generates_multiple_waypoints(self):
        wps = WaypointPlanner.expanding_square(47.3977, 8.5456, 20, 15, 100, 20)
        assert len(wps) > 1

    def test_starts_at_center(self):
        lat, lon = 47.3977, 8.5456
        wps = WaypointPlanner.expanding_square(lat, lon, 20, 15, 100, 20)
        assert wps[0].latitude == lat
        assert wps[0].longitude == lon


class TestCustomWaypoints:
    """Test custom waypoint loading."""

    def test_loads_from_dicts(self):
        dicts = [
            {"lat": 47.3977, "lon": 8.5456},
            {"lat": 47.3980, "lon": 8.5460},
        ]
        wps = WaypointPlanner.custom_waypoints(dicts, altitude_m=15)
        assert len(wps) == 2
        assert wps[0].latitude == 47.3977

    def test_per_waypoint_altitude(self):
        dicts = [{"lat": 47.3977, "lon": 8.5456, "alt": 30.0}]
        wps = WaypointPlanner.custom_waypoints(dicts, altitude_m=15)
        assert wps[0].altitude == 30.0


class TestGPSOffset:
    """Test GPS offset calculations from core.geo."""

    def test_zero_offset_same_point(self):
        lat, lon = offset_gps(47.3977, 8.5456, 0, 0)
        assert lat == 47.3977
        assert lon == 8.5456

    def test_north_offset_increases_lat(self):
        lat, lon = offset_gps(47.3977, 8.5456, 100, 0)
        assert lat > 47.3977

    def test_east_offset_increases_lon(self):
        lat, lon = offset_gps(47.3977, 8.5456, 0, 100)
        assert lon > 8.5456


# ── Strategy Pattern Tests ───────────────────────────────────

class TestPatternRegistry:
    """Test the Strategy pattern registry."""

    def test_lawnmower_registered(self):
        assert "lawnmower" in PatternRegistry.available()

    def test_expanding_square_registered(self):
        assert "expanding_square" in PatternRegistry.available()

    def test_custom_registered(self):
        assert "custom" in PatternRegistry.available()

    def test_generate_lawnmower(self):
        config = {
            "center_lat": 47.3977, "center_lon": 8.5456,
            "width_m": 100, "height_m": 100,
            "spacing_m": 20, "altitude_m": 15,
        }
        wps = PatternRegistry.generate("lawnmower", config)
        assert len(wps) > 0

    def test_unknown_pattern_raises(self):
        try:
            PatternRegistry.generate("nonexistent", {})
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_strategy_interface(self):
        """Verify each pattern implements the interface correctly."""
        pattern = PatternRegistry.get("lawnmower")
        assert pattern is not None
        assert hasattr(pattern, "name")
        assert hasattr(pattern, "generate")
        assert pattern.name == "lawnmower"
