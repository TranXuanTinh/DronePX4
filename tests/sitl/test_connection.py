"""
SITL Connection tests — verify connectivity to PX4 SITL.

DO-178C Traceability: REQ-SITL-CONN-001 through REQ-SITL-CONN-005
"""
import asyncio
import pytest


@pytest.mark.sitl
@pytest.mark.timeout(60)
class TestSITLConnection:
    """Test PX4 SITL connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_successfully(self, sitl_bridge):
        """REQ-SITL-CONN-001: Connect to SITL on first attempt."""
        assert sitl_bridge.is_connected is True

    @pytest.mark.asyncio
    async def test_telemetry_available_after_stream_start(self, sitl_ready):
        """REQ-SITL-CONN-002: Telemetry is populated after stream start."""
        await sitl_ready.start_telemetry_stream(rate_hz=10.0)
        await asyncio.sleep(1.0)  # Allow stream to populate

        telem = sitl_ready.latest_telemetry
        assert telem is not None
        assert telem.gps_fix_type >= 3

        await sitl_ready.stop_telemetry_stream()

    @pytest.mark.asyncio
    async def test_gps_fix_type_3d(self, sitl_ready):
        """REQ-SITL-CONN-003: GPS fix type is at least 3D."""
        await sitl_ready.start_telemetry_stream(rate_hz=10.0)
        await asyncio.sleep(1.0)

        telem = sitl_ready.latest_telemetry
        assert telem is not None
        assert telem.gps_fix_type >= 3, (
            f"GPS fix type {telem.gps_fix_type} < 3 (no 3D fix)"
        )

        await sitl_ready.stop_telemetry_stream()

    @pytest.mark.asyncio
    async def test_is_healthy_returns_true_when_connected(self, sitl_bridge):
        """REQ-SITL-CONN-004: is_healthy() returns True when SITL running."""
        result = await sitl_bridge.is_healthy()
        assert result is True

    @pytest.mark.asyncio
    async def test_disconnect_and_verify(self, sitl_bridge):
        """REQ-SITL-CONN-005: Disconnect clears connected flag."""
        assert sitl_bridge.is_connected is True
        await sitl_bridge.disconnect()
        assert sitl_bridge.is_connected is False
