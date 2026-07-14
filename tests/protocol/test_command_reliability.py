"""
Command reliability tests.

Validates that flight commands are reliably delivered and that
the retry mechanism handles transient failures.

DO-178C Traceability: REQ-PROTO-010 through REQ-PROTO-012
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.protocol
class TestCommandReliability:
    """Test command delivery reliability."""

    def _make_flight_commands(self):
        """Create FlightCommands with mocked bridge."""
        bridge = MagicMock()
        bridge.drone = MagicMock()
        bridge.reconnect = AsyncMock(return_value=True)

        with patch("src.bridge.commands.MAVLinkBridge"):
            from src.bridge.commands import FlightCommands
            cmd = FlightCommands(bridge)
        return cmd, bridge

    @pytest.mark.asyncio
    async def test_sequential_commands_all_execute(self):
        """REQ-PROTO-010: Rapid sequential commands all succeed."""
        cmd, bridge = self._make_flight_commands()
        cmd._drone.action.arm = AsyncMock()
        cmd._drone.action.set_takeoff_altitude = AsyncMock()
        cmd._drone.action.takeoff = AsyncMock()
        cmd._drone.action.hold = AsyncMock()
        cmd._drone.action.return_to_launch = AsyncMock()

        # Execute rapid sequence
        await cmd.arm()
        await cmd.takeoff(15.0)
        await cmd.hold()
        await cmd.rtl()

        cmd._drone.action.arm.assert_called_once()
        cmd._drone.action.takeoff.assert_called_once()
        cmd._drone.action.hold.assert_called_once()
        cmd._drone.action.return_to_launch.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_recovers_from_transient_error(self):
        """REQ-PROTO-011: Single transient error is recovered via retry."""
        cmd, bridge = self._make_flight_commands()
        call_count = 0

        async def _flaky():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("UNAVAILABLE: transient")

        cmd._drone.action.arm = _flaky

        await cmd.arm()
        assert call_count == 2
        bridge.reconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_goto_commands_no_crash(self):
        """REQ-PROTO-012: Multiple rapid goto commands don't crash."""
        cmd, bridge = self._make_flight_commands()
        cmd._drone.action.goto_location = AsyncMock()

        # Send 20 rapid goto commands
        for i in range(20):
            lat = 47.3977 + i * 0.0001
            await cmd.goto(lat, 8.5456, 20.0)

        assert cmd._drone.action.goto_location.call_count == 20
