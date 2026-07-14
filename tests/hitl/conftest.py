"""
HITL test fixtures — stubs for future hardware-in-the-loop testing.

All fixtures are marked with @pytest.mark.hitl and will be
automatically skipped when hardware is not available.
"""
import os
import pytest


def _hitl_port() -> str:
    """Get HITL serial port from environment."""
    return os.environ.get("PX4_HITL_PORT", "/dev/ttyACM0")


def _hitl_baud() -> int:
    """Get HITL baud rate from environment."""
    return int(os.environ.get("PX4_HITL_BAUD", "921600"))


@pytest.fixture
def hitl_connection():
    """Connect to physical Pixhawk via serial.

    Stub — will be implemented when HITL hardware is available.
    """
    pytest.skip("HITL hardware not available — stub fixture")
    yield None


@pytest.fixture
def hitl_sensor_injector():
    """Inject virtual sensor data into Pixhawk HITL mode.

    Stub — will be implemented when HITL hardware is available.
    """
    pytest.skip("HITL hardware not available — stub fixture")
    yield None
