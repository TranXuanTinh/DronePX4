"""
Root pytest configuration — shared fixtures, markers, and SITL skip logic.

Provides:
- Custom markers: unit, integration, sitl, failsafe, protocol, hitl
- SITL auto-skip when PX4 is not running
- Shared telemetry factory fixtures used across all test layers
- Mock drone subsystem fixtures (connector, flight controller, etc.)

DO-178C Alignment:
    This conftest establishes the test infrastructure required for
    bi-directional traceability between requirements and test cases.
"""
from __future__ import annotations

import asyncio
import socket
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import numpy as np
import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = str(Path(__file__).parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.types import (
    TelemetryFrame, Position, Attitude, Detection, Track,
    GeotaggedDetection, SafetyAction, MissionState, Waypoint,
    StateChangeEvent, TelemetryEvent, DetectionFoundEvent,
)
from src.core.events import EventBus


# ──────────────────────────────────────────────────────────────
# Disable conflicting ROS launch_testing plugins
# ──────────────────────────────────────────────────────────────
collect_ignore_glob = ["**/launch_testing*"]


# ──────────────────────────────────────────────────────────────
# SITL Availability Detection
# ──────────────────────────────────────────────────────────────

def _is_sitl_available(host: str = "127.0.0.1", port: int = 14540) -> bool:
    """Check if PX4 SITL is reachable on the MAVLink UDP port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        # Send a MAVLink heartbeat probe — if SITL is running,
        # the port is bound and no error is raised.
        sock.sendto(b"\x00", (host, port))
        sock.close()
        return True
    except (OSError, socket.timeout):
        return False


def pytest_configure(config):
    """Register custom markers for all test layers."""
    config.addinivalue_line("markers", "unit: Unit tests (no SITL required)")
    config.addinivalue_line("markers", "integration: Integration tests (no SITL)")
    config.addinivalue_line("markers", "sitl: SITL end-to-end tests (requires PX4)")
    config.addinivalue_line("markers", "failsafe: Failsafe & emergency scenario tests")
    config.addinivalue_line("markers", "protocol: Communication protocol tests")
    config.addinivalue_line("markers", "hitl: Hardware-in-the-loop tests (future)")


def pytest_collection_modifyitems(config, items):
    """Auto-skip SITL and HITL tests when hardware/simulator unavailable."""
    sitl_available = _is_sitl_available()

    skip_sitl = pytest.mark.skip(reason="PX4 SITL not running (start with ./scripts/launch_sitl.sh)")
    skip_hitl = pytest.mark.skip(reason="HITL hardware not available")

    for item in items:
        if "sitl" in item.keywords and not sitl_available:
            item.add_marker(skip_sitl)
        if "hitl" in item.keywords:
            item.add_marker(skip_hitl)


# ──────────────────────────────────────────────────────────────
# Telemetry Factory Fixture
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def make_telemetry():
    """Factory fixture for creating TelemetryFrame instances.

    Usage:
        def test_something(make_telemetry):
            telem = make_telemetry(battery=15.0, alt=150.0)
    """
    def _factory(
        lat: float = 47.397742,
        lon: float = 8.545594,
        abs_alt: float = 488.0,
        alt: float = 15.0,
        battery: float = 80.0,
        connected: bool = True,
        armed: bool = True,
        heading: float = 0.0,
        speed: float = 5.0,
        flight_mode: str = "OFFBOARD",
        gps_sats: int = 12,
        gps_fix: int = 3,
        voltage: float = 16.0,
        timestamp: float = 0.0,
    ) -> TelemetryFrame:
        return TelemetryFrame(
            timestamp=timestamp,
            position=Position(lat, lon, abs_alt, alt),
            attitude=Attitude(0.0, 0.0, heading),
            heading_deg=heading,
            groundspeed_ms=speed,
            battery_percent=battery,
            battery_voltage=voltage,
            flight_mode=flight_mode,
            armed=armed,
            is_connected=connected,
            gps_num_satellites=gps_sats,
            gps_fix_type=gps_fix,
        )
    return _factory


# ──────────────────────────────────────────────────────────────
# Mock Drone Subsystem Fixtures
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_connector(make_telemetry):
    """Mock DroneConnector with sensible defaults."""
    connector = MagicMock()
    connector.is_connected = True
    connector.latest_telemetry = make_telemetry()
    connector.connect = AsyncMock()
    connector.disconnect = AsyncMock()
    connector.wait_for_ready = AsyncMock()
    connector.start_telemetry_stream = AsyncMock()
    connector.stop_telemetry_stream = AsyncMock()
    connector.is_healthy = AsyncMock(return_value=True)
    connector.reconnect = AsyncMock(return_value=True)
    return connector


@pytest.fixture
def mock_flight():
    """Mock FlightController with all async methods."""
    flight = MagicMock()
    flight.arm = AsyncMock()
    flight.disarm = AsyncMock()
    flight.takeoff = AsyncMock()
    flight.land = AsyncMock()
    flight.rtl = AsyncMock()
    flight.hold = AsyncMock()
    flight.goto = AsyncMock()
    flight.wait_for_altitude = AsyncMock(return_value=True)
    flight.wait_for_landed = AsyncMock(return_value=True)
    flight.is_offboard_active = False
    flight.stop_offboard = AsyncMock()
    flight._refresh_drone_ref = MagicMock()
    return flight


@pytest.fixture
def mock_detector():
    """Mock ObjectDetector that returns no detections by default."""
    detector = MagicMock()
    detector.detect = MagicMock(return_value=[])
    detector.load = MagicMock()
    detector.avg_inference_ms = 5.0
    return detector


@pytest.fixture
def mock_tracker():
    """Mock ObjectTracker that returns no tracks by default."""
    tracker = MagicMock()
    tracker.update = MagicMock(return_value=[])
    tracker.reset = MagicMock()
    return tracker


@pytest.fixture
def mock_geotagger():
    """Mock Geotagger."""
    return MagicMock()


@pytest.fixture
def mock_camera():
    """Mock CameraSource that returns None (no frame) by default."""
    camera = MagicMock()
    camera.open = MagicMock(return_value=True)
    camera.get_frame = MagicMock(return_value=None)
    camera.release = MagicMock()
    camera.frame_count = 0
    return camera


@pytest.fixture
def mock_safety():
    """Mock SafetyChecker that returns NONE (safe) by default."""
    safety = MagicMock()
    safety.check = MagicMock(return_value=SafetyAction.NONE)
    return safety


@pytest.fixture
def event_bus():
    """Fresh EventBus instance."""
    return EventBus()


@pytest.fixture
def default_config():
    """Default mission configuration matching sim_config.yaml."""
    return {
        "takeoff_altitude_m": 15.0,
        "search_altitude_m": 20.0,
        "inspect_altitude_m": 8.0,
        "max_speed_ms": 5.0,
        "detection_confirm_frames": 5,
        "detection_confirm_timeout_s": 3.0,
        "search_area": {
            "center_lat": 47.397742,
            "center_lon": 8.545594,
            "width_m": 200,
            "height_m": 150,
            "spacing_m": 30,
        },
        "search_pattern": "lawnmower",
    }


@pytest.fixture
def sample_waypoints():
    """Small set of test waypoints near SITL default home."""
    return [
        Waypoint(latitude=47.397742, longitude=8.545594, altitude=20.0, index=0),
        Waypoint(latitude=47.398042, longitude=8.545594, altitude=20.0, index=1),
        Waypoint(latitude=47.398042, longitude=8.546094, altitude=20.0, index=2),
    ]


@pytest.fixture
def sample_detection():
    """A sample Detection for testing."""
    return Detection(
        bbox=np.array([100, 150, 200, 250]),
        class_id=0,
        class_name="person",
        confidence=0.85,
    )


@pytest.fixture
def sample_track():
    """A sample confirmed Track for testing."""
    return Track(
        track_id=1,
        bbox=np.array([100, 150, 200, 250]),
        class_id=0,
        class_name="person",
        confidence=0.85,
        age=10,
        is_confirmed=True,
    )


@pytest.fixture
def sample_geotagged_detection():
    """A sample GeotaggedDetection for testing."""
    return GeotaggedDetection(
        track_id=1,
        class_name="person",
        confidence=0.85,
        bbox=np.array([100, 150, 200, 250]),
        pixel_center=(150, 200),
        latitude_deg=47.397800,
        longitude_deg=8.545650,
        drone_altitude_m=20.0,
        timestamp=1000.0,
    )
