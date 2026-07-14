"""
Unit tests for FlightCommands — gRPC retry, reconnect, command wrappers.

DO-178C Traceability: REQ-FLIGHT-001 through REQ-FLIGHT-008
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


@pytest.mark.unit
class TestFlightCommandsRetry:
    """Test gRPC retry and reconnection logic."""

    def _make_flight_commands(self, mock_bridge=None):
        """Create a FlightCommands with a mocked bridge."""
        bridge = mock_bridge or MagicMock()
        bridge.drone = MagicMock()
        bridge.reconnect = AsyncMock(return_value=True)

        with patch("src.bridge.commands.MAVLinkBridge"):
            from src.bridge.commands import FlightCommands
            cmd = FlightCommands(bridge)
        return cmd, bridge

    @pytest.mark.asyncio
    async def test_arm_success(self):
        """REQ-FLIGHT-001: arm() calls drone.action.arm()."""
        cmd, bridge = self._make_flight_commands()
        cmd._drone.action.arm = AsyncMock()
        await cmd.arm()
        cmd._drone.action.arm.assert_called_once()

    @pytest.mark.asyncio
    async def test_disarm_success(self):
        """REQ-FLIGHT-002: disarm() calls drone.action.disarm()."""
        cmd, bridge = self._make_flight_commands()
        cmd._drone.action.disarm = AsyncMock()
        await cmd.disarm()
        cmd._drone.action.disarm.assert_called_once()

    @pytest.mark.asyncio
    async def test_takeoff_sets_altitude(self):
        """REQ-FLIGHT-003: takeoff() sets altitude and calls takeoff."""
        cmd, bridge = self._make_flight_commands()
        cmd._drone.action.set_takeoff_altitude = AsyncMock()
        cmd._drone.action.takeoff = AsyncMock()

        await cmd.takeoff(25.0)
        cmd._drone.action.set_takeoff_altitude.assert_called_once_with(25.0)
        cmd._drone.action.takeoff.assert_called_once()

    @pytest.mark.asyncio
    async def test_rtl_success(self):
        """REQ-FLIGHT-004: rtl() calls return_to_launch()."""
        cmd, bridge = self._make_flight_commands()
        cmd._drone.action.return_to_launch = AsyncMock()
        await cmd.rtl()
        cmd._drone.action.return_to_launch.assert_called_once()

    @pytest.mark.asyncio
    async def test_hold_stops_offboard_first(self):
        """REQ-FLIGHT-005: hold() stops offboard if active."""
        cmd, bridge = self._make_flight_commands()
        cmd._offboard_active = True
        cmd._drone.offboard.stop = AsyncMock()
        cmd._drone.action.hold = AsyncMock()

        await cmd.hold()
        cmd._drone.offboard.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_goto_sends_location(self):
        """REQ-FLIGHT-006: goto() sends lat/lon/alt coordinates."""
        cmd, bridge = self._make_flight_commands()
        cmd._drone.action.goto_location = AsyncMock()

        await cmd.goto(47.3977, 8.5456, 20.0, 90.0)
        cmd._drone.action.goto_location.assert_called_once_with(
            47.3977, 8.5456, 20.0, 90.0
        )

    @pytest.mark.asyncio
    async def test_retry_on_grpc_unavailable(self):
        """REQ-FLIGHT-007: Retries command on gRPC UNAVAILABLE error."""
        cmd, bridge = self._make_flight_commands()
        call_count = 0

        async def _flaky_arm():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("UNAVAILABLE: connection refused")
            return None

        cmd._drone.action.arm = _flaky_arm
        bridge.reconnect = AsyncMock(return_value=True)

        await cmd.arm()
        assert call_count == 2
        bridge.reconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_retry_on_action_error(self):
        """REQ-FLIGHT-008: ActionError is not retried (real drone error)."""
        cmd, bridge = self._make_flight_commands()

        from mavsdk.action import ActionError
        action_result = MagicMock()
        action_result.result = "COMMAND_DENIED"
        action_result.result_str = "Command denied"

        cmd._drone.action.arm = AsyncMock(
            side_effect=ActionError(action_result, "Denied")
        )

        with pytest.raises(ActionError):
            await cmd.arm()
        # Should NOT have attempted reconnect
        bridge.reconnect.assert_not_called()


@pytest.mark.unit
class TestFlightCommandsRefresh:
    """Test drone reference refresh after reconnection."""

    def test_refresh_drone_ref_updates_reference(self):
        """REQ-FLIGHT-007: _refresh_drone_ref updates internal drone ref."""
        bridge = MagicMock()
        bridge.drone = MagicMock(name="original_drone")

        with patch("src.bridge.commands.MAVLinkBridge"):
            from src.bridge.commands import FlightCommands
            cmd = FlightCommands(bridge)

        new_drone = MagicMock(name="new_drone")
        bridge.drone = new_drone

        cmd._refresh_drone_ref()
        assert cmd._drone is new_drone
