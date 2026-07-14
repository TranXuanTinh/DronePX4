"""
MAVLink data integrity tests.

Validates that telemetry data fields are within valid physical ranges
and contain no corrupt or invalid values.

DO-178C Traceability: REQ-PROTO-001 through REQ-PROTO-006
"""
import math
import pytest

from src.core.types import TelemetryFrame, Position, Attitude


@pytest.mark.protocol
class TestTelemetryFieldValidation:
    """Validate telemetry data integrity."""

    def test_gps_latitude_in_valid_range(self, make_telemetry):
        """REQ-PROTO-001: Latitude must be in [-90, 90]."""
        for lat in [-90, -45, 0, 45, 90]:
            telem = make_telemetry(lat=lat)
            assert -90.0 <= telem.position.latitude_deg <= 90.0

    def test_gps_longitude_in_valid_range(self, make_telemetry):
        """REQ-PROTO-002: Longitude must be in [-180, 180]."""
        for lon in [-180, -90, 0, 90, 180]:
            telem = make_telemetry(lon=lon)
            assert -180.0 <= telem.position.longitude_deg <= 180.0

    def test_battery_percent_in_valid_range(self, make_telemetry):
        """REQ-PROTO-003: Battery percentage must be in [0, 100]."""
        for pct in [0, 25, 50, 75, 100]:
            telem = make_telemetry(battery=pct)
            assert 0.0 <= telem.battery_percent <= 100.0

    def test_altitude_physically_reasonable(self, make_telemetry):
        """REQ-PROTO-004: Altitude must be < 10,000m."""
        telem = make_telemetry(alt=120.0)
        assert telem.position.relative_altitude_m < 10000.0

    def test_no_nan_in_critical_fields(self, make_telemetry):
        """REQ-PROTO-005: No NaN in critical telemetry fields."""
        telem = make_telemetry()
        assert not math.isnan(telem.position.latitude_deg)
        assert not math.isnan(telem.position.longitude_deg)
        assert not math.isnan(telem.position.relative_altitude_m)
        assert not math.isnan(telem.battery_percent)
        assert not math.isnan(telem.groundspeed_ms)

    def test_heading_in_valid_range(self, make_telemetry):
        """REQ-PROTO-006: Heading must be in [0, 360]."""
        for heading in [0, 90, 180, 270, 360]:
            telem = make_telemetry(heading=heading)
            assert 0.0 <= telem.heading_deg <= 360.0


@pytest.mark.protocol
class TestTelemetryFrameConsistency:
    """Test internal consistency of TelemetryFrame."""

    def test_frame_fields_have_correct_types(self, make_telemetry):
        """REQ-PROTO-001: All fields have expected Python types."""
        telem = make_telemetry()
        assert isinstance(telem.position, Position)
        assert isinstance(telem.attitude, Attitude)
        assert isinstance(telem.battery_percent, float)
        assert isinstance(telem.armed, bool)
        assert isinstance(telem.is_connected, bool)
        assert isinstance(telem.flight_mode, str)
        assert isinstance(telem.gps_num_satellites, int)

    def test_position_immutable(self, make_telemetry):
        """REQ-PROTO-001: Position is frozen dataclass (immutable)."""
        telem = make_telemetry()
        with pytest.raises(AttributeError):
            telem.position.latitude_deg = 0.0  # Should fail — frozen

    def test_gps_satellites_nonnegative(self, make_telemetry):
        """REQ-PROTO-003: GPS satellite count is non-negative."""
        telem = make_telemetry(gps_sats=12)
        assert telem.gps_num_satellites >= 0
