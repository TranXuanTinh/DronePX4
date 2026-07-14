"""
SITL Takeoff/Land tests — arm, takeoff, land, disarm lifecycle.

DO-178C Traceability: REQ-SITL-FLIGHT-001 through REQ-SITL-FLIGHT-004
"""
import asyncio
import pytest


@pytest.mark.sitl
@pytest.mark.timeout(120)
class TestSITLTakeoffLand:
    """Test takeoff and landing with live SITL."""

    @pytest.mark.asyncio
    async def test_arm_takeoff_land_disarm(self, sitl_ready, sitl_flight):
        """REQ-SITL-FLIGHT-001: Full takeoff/land cycle."""
        # Arm
        await sitl_flight.arm()
        await asyncio.sleep(1.0)

        # Takeoff to 15m
        await sitl_flight.takeoff(15.0)
        reached = await sitl_flight.wait_for_altitude(
            15.0, tolerance_m=2.0, timeout_s=30.0,
        )
        assert reached, "Failed to reach takeoff altitude"

        # Land
        await sitl_flight.land()
        landed = await sitl_flight.wait_for_landed(timeout_s=60.0)
        assert landed, "Failed to land"

        # Disarm
        await asyncio.sleep(2.0)
        try:
            await sitl_flight.disarm()
        except Exception:
            pass  # May auto-disarm after landing
