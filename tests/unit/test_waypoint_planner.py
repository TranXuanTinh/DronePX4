"""Unit tests for the waypoint planner.

No external dependencies — tests pure Python math.
"""

import pytest
import sys
import math
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mission.waypoint_planner import WaypointPlanner, Waypoint


class TestLawnmowerPattern:
    """Test lawnmower search pattern generation."""

    def test_generates_waypoints(self):
        wps = WaypointPlanner.lawnmower(
            center_lat=47.0, center_lon=8.0,
            width_m=100, height_m=100,
            spacing_m=50, altitude_m=20,
        )
        assert len(wps) > 0
        assert all(isinstance(w, Waypoint) for w in wps)

    def test_altitude_set_correctly(self):
        wps = WaypointPlanner.lawnmower(47.0, 8.0, 100, 100, 50, 25.0)
        assert all(w.altitude == 25.0 for w in wps)

    def test_waypoints_near_center(self):
        wps = WaypointPlanner.lawnmower(47.0, 8.0, 100, 100, 50, 20)
        for wp in wps:
            assert abs(wp.latitude - 47.0) < 0.01
            assert abs(wp.longitude - 8.0) < 0.01

    def test_indices_sequential(self):
        wps = WaypointPlanner.lawnmower(47.0, 8.0, 100, 100, 30, 20)
        indices = [w.index for w in wps]
        assert indices == list(range(len(wps)))

    def test_wider_area_more_passes(self):
        narrow = WaypointPlanner.lawnmower(47.0, 8.0, 50, 100, 30, 20)
        wide = WaypointPlanner.lawnmower(47.0, 8.0, 200, 100, 30, 20)
        assert len(wide) > len(narrow)


class TestExpandingSquare:
    """Test expanding square search pattern."""

    def test_starts_at_center(self):
        wps = WaypointPlanner.expanding_square(
            47.0, 8.0, initial_radius_m=20,
            expansion_m=15, max_radius_m=50, altitude_m=20,
        )
        assert wps[0].latitude == pytest.approx(47.0, abs=0.0001)
        assert wps[0].longitude == pytest.approx(8.0, abs=0.0001)

    def test_generates_multiple_waypoints(self):
        wps = WaypointPlanner.expanding_square(
            47.0, 8.0, 20, 15, 100, 20,
        )
        assert len(wps) > 5


class TestCustomWaypoints:
    """Test custom waypoint loading."""

    def test_loads_from_dicts(self):
        data = [
            {"lat": 47.0, "lon": 8.0},
            {"lat": 47.001, "lon": 8.001},
            {"lat": 47.002, "lon": 8.002},
        ]
        wps = WaypointPlanner.custom_waypoints(data, altitude_m=15)
        assert len(wps) == 3
        assert wps[0].latitude == 47.0
        assert wps[2].altitude == 15

    def test_per_waypoint_altitude(self):
        data = [
            {"lat": 47.0, "lon": 8.0, "alt": 10},
            {"lat": 47.001, "lon": 8.001, "alt": 25},
        ]
        wps = WaypointPlanner.custom_waypoints(data, altitude_m=20)
        assert wps[0].altitude == 10
        assert wps[1].altitude == 25


class TestGPSOffset:
    """Test GPS meter offset calculations."""

    def test_zero_offset_same_point(self):
        lat, lon = WaypointPlanner._offset_gps(47.0, 8.0, 0, 0)
        assert lat == pytest.approx(47.0, abs=1e-10)
        assert lon == pytest.approx(8.0, abs=1e-10)

    def test_north_offset_increases_lat(self):
        lat, lon = WaypointPlanner._offset_gps(47.0, 8.0, 100, 0)
        assert lat > 47.0

    def test_east_offset_increases_lon(self):
        lat, lon = WaypointPlanner._offset_gps(47.0, 8.0, 0, 100)
        assert lon > 8.0
