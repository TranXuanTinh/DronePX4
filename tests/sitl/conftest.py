"""
SITL test fixtures — connection, lifecycle, auto-skip.

All tests in this package require PX4 SITL running.
They are automatically skipped when the simulator is not available.
"""
import asyncio
import pytest

from src.bridge.mavlink_bridge import MAVLinkBridge
from src.bridge.commands import FlightCommands


@pytest.fixture
async def sitl_bridge():
    """Connect to PX4 SITL, yield bridge, disconnect on teardown.

    Auto-skips if SITL is not running.
    """
    bridge = MAVLinkBridge()
    try:
        await asyncio.wait_for(bridge.connect(), timeout=15.0)
    except (ConnectionError, TimeoutError, asyncio.TimeoutError):
        pytest.skip("PX4 SITL not available")

    yield bridge

    await bridge.disconnect()


@pytest.fixture
async def sitl_flight(sitl_bridge):
    """FlightCommands connected to live SITL."""
    return FlightCommands(sitl_bridge)


@pytest.fixture
async def sitl_ready(sitl_bridge):
    """Ensure SITL has GPS fix and home position set."""
    try:
        await asyncio.wait_for(sitl_bridge.wait_for_ready(), timeout=30.0)
    except (TimeoutError, asyncio.TimeoutError):
        pytest.skip("SITL did not become ready (no GPS fix)")

    return sitl_bridge
