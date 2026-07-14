"""
SITL Waypoint Navigation tests — navigate waypoints, verify GPS arrival.

DO-178C Traceability: REQ-SITL-NAV-001 through REQ-SITL-NAV-003
"""
import asyncio
import pytest

from src.core.geo import haversine_distance
from src.mission.waypoint_planner import WaypointPlanner


@pytest.mark.sitl
@pytest.mark.timeout(180)
class TestSITLWaypointNavigation:
    """Test waypoint navigation with live SITL."""

    @pytest.mark.asyncio
    async def test_navigate_to_single_waypoint(self, sitl_ready, sitl_flight):
        """REQ-SITL-NAV-001: Navigate to a waypoint within 5m accuracy."""
        # Arm and takeoff
        await sitl_flight.arm()
        await sitl_flight.takeoff(20.0)
        reached = await sitl_flight.wait_for_altitude(20.0, tolerance_m=3.0, timeout_s=30.0)
        assert reached, "Failed to reach takeoff altitude"

        # Navigate to a waypoint 50m north
        target_lat = 47.398242
        target_lon = 8.545594
        await sitl_flight.goto(target_lat, target_lon, 20.0)

        # Wait for arrival (check every 2s for up to 60s)
        for _ in range(30):
            await asyncio.sleep(2.0)
            telem = sitl_ready.latest_telemetry
            if telem:
                dist = haversine_distance(
                    telem.position.latitude_deg,
                    telem.position.longitude_deg,
                    target_lat, target_lon,
                )
                if dist < 5.0:
                    break
        else:
            pytest.fail("Did not reach waypoint within timeout")

        # RTL cleanup
        await sitl_flight.rtl()
        await sitl_flight.wait_for_landed(timeout_s=60.0)


@pytest.mark.sitl
@pytest.mark.timeout(300)
class TestSITLMultiWaypoint:
    """Test multi-waypoint navigation."""

    @pytest.mark.asyncio
    async def test_lawnmower_3_waypoints(self, sitl_ready, sitl_flight):
        """REQ-SITL-NAV-002: Navigate 3 lawnmower waypoints in sequence."""
        waypoints = WaypointPlanner.lawnmower(
            center_lat=47.397742, center_lon=8.545594,
            width_m=60, height_m=40, spacing_m=30, altitude_m=20.0,
        )[:3]  # Take only first 3 for speed

        # Arm and takeoff
        await sitl_flight.arm()
        await sitl_flight.takeoff(20.0)
        reached = await sitl_flight.wait_for_altitude(20.0, tolerance_m=3.0, timeout_s=30.0)
        assert reached

        visited = 0
        for wp in waypoints:
            await sitl_flight.goto(wp.latitude, wp.longitude, wp.altitude)

            for _ in range(30):
                await asyncio.sleep(2.0)
                telem = sitl_ready.latest_telemetry
                if telem:
                    dist = haversine_distance(
                        telem.position.latitude_deg,
                        telem.position.longitude_deg,
                        wp.latitude, wp.longitude,
                    )
                    if dist < 5.0:
                        visited += 1
                        break

        assert visited == 3, f"Only visited {visited}/3 waypoints"

        # Cleanup
        await sitl_flight.rtl()
        await sitl_flight.wait_for_landed(timeout_s=60.0)
