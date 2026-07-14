"""
Unit tests for MissionExecutor — state handler methods.

DO-178C Traceability: REQ-EXEC-001 through REQ-EXEC-012
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.core.types import (
    SafetyAction, TelemetryFrame, Position, Attitude,
    Detection, Track, GeotaggedDetection,
)
from src.mission.executor import MissionExecutor


def _create_executor(
    mock_connector, mock_flight, mock_detector, mock_tracker,
    mock_geotagger, mock_camera, mock_safety, default_config,
    event_bus=None,
):
    """Helper to construct a MissionExecutor with injected mocks."""
    return MissionExecutor(
        connector=mock_connector,
        flight=mock_flight,
        detector=mock_detector,
        tracker=mock_tracker,
        geotagger=mock_geotagger,
        camera=mock_camera,
        safety=mock_safety,
        config=default_config,
        event_bus=event_bus,
    )


@pytest.mark.unit
class TestDoPreFlight:
    """Test PREFLIGHT state handler."""

    @pytest.mark.asyncio
    async def test_preflight_pass_when_connected_and_gps(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config, make_telemetry,
    ):
        """REQ-EXEC-001: checks_pass when connected with GPS fix."""
        mock_connector.latest_telemetry = make_telemetry(gps_fix=3)
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        result = await executor.do_preflight()
        assert result == "checks_pass"

    @pytest.mark.asyncio
    async def test_preflight_fail_when_disconnected(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-EXEC-002: checks_fail when not connected."""
        mock_connector.is_connected = False
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        result = await executor.do_preflight()
        assert result == "checks_fail"

    @pytest.mark.asyncio
    async def test_preflight_fail_no_gps_fix(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config, make_telemetry,
    ):
        """REQ-EXEC-003: checks_fail when GPS fix type < 3."""
        mock_connector.latest_telemetry = make_telemetry(gps_fix=1)
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        result = await executor.do_preflight()
        assert result == "checks_fail"

    @pytest.mark.asyncio
    async def test_preflight_reconnects_when_unhealthy(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config, make_telemetry,
    ):
        """REQ-EXEC-004: Triggers reconnect when gRPC channel unhealthy."""
        mock_connector.is_healthy = AsyncMock(return_value=False)
        mock_connector.reconnect = AsyncMock(return_value=True)
        mock_connector.latest_telemetry = make_telemetry(gps_fix=3)

        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        result = await executor.do_preflight()
        mock_connector.reconnect.assert_called_once()
        assert result == "checks_pass"


@pytest.mark.unit
class TestDoTakeoff:
    """Test TAKEOFF state handler."""

    @pytest.mark.asyncio
    async def test_takeoff_success(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-EXEC-005: Arm → takeoff → altitude_reached."""
        mock_flight.wait_for_altitude = AsyncMock(return_value=True)
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        result = await executor.do_takeoff()
        mock_flight.arm.assert_called_once()
        mock_flight.takeoff.assert_called_once_with(15.0)
        assert result == "altitude_reached"

    @pytest.mark.asyncio
    async def test_takeoff_abort_on_connection_error(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-EXEC-006: Returns 'abort' on ConnectionError."""
        mock_flight.arm = AsyncMock(side_effect=ConnectionError("gRPC down"))
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        result = await executor.do_takeoff()
        assert result == "abort"

    @pytest.mark.asyncio
    async def test_takeoff_abort_on_altitude_timeout(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-EXEC-006: Returns 'abort' when altitude not reached."""
        mock_flight.wait_for_altitude = AsyncMock(return_value=False)
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        result = await executor.do_takeoff()
        assert result == "abort"


@pytest.mark.unit
class TestDoSearch:
    """Test SEARCH state handler."""

    @pytest.mark.asyncio
    async def test_search_complete_when_all_waypoints_visited(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config, sample_waypoints,
    ):
        """REQ-EXEC-007: Returns search_complete when no more waypoints."""
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        executor.waypoints = sample_waypoints
        executor.current_waypoint_idx = len(sample_waypoints)
        result = await executor.do_search()
        assert result == "search_complete"

    @pytest.mark.asyncio
    async def test_search_safety_rtl_on_violation(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config, sample_waypoints, make_telemetry,
    ):
        """REQ-EXEC-008: Returns safety_rtl when safety check triggers."""
        mock_safety.check = MagicMock(return_value=SafetyAction.RTL_NOW)
        mock_connector.latest_telemetry = make_telemetry()

        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        executor.waypoints = sample_waypoints
        executor.current_waypoint_idx = 0

        result = await executor.do_search()
        assert result == "safety_rtl"

    @pytest.mark.asyncio
    async def test_search_detects_object(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config, sample_waypoints,
        make_telemetry, sample_track, sample_geotagged_detection,
    ):
        """REQ-EXEC-009: Returns object_detected when confirmed track found."""
        mock_connector.latest_telemetry = make_telemetry()
        mock_camera.get_frame = MagicMock(
            return_value=np.zeros((480, 640, 3), dtype=np.uint8)
        )
        mock_detector.detect = MagicMock(return_value=[MagicMock()])
        mock_tracker.update = MagicMock(return_value=[sample_track])
        mock_geotagger.tag_detections = MagicMock(
            return_value=[sample_geotagged_detection]
        )

        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        executor.waypoints = sample_waypoints
        executor.current_waypoint_idx = 0

        result = await executor.do_search()
        assert result == "object_detected"
        assert executor.pending_detection is not None


@pytest.mark.unit
class TestDoLog:
    """Test LOG state handler."""

    @pytest.mark.asyncio
    async def test_log_appends_detection(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config, sample_geotagged_detection,
        make_telemetry, sample_waypoints,
    ):
        """REQ-EXEC-010: Pending detection is appended to detections list."""
        mock_connector.latest_telemetry = make_telemetry()
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        executor.pending_detection = sample_geotagged_detection
        executor.waypoints = sample_waypoints
        executor.current_waypoint_idx = 0

        result = await executor.do_log()
        assert len(executor.detections) == 1
        assert result == "more_waypoints"

    @pytest.mark.asyncio
    async def test_log_mission_complete_no_more_waypoints(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config, make_telemetry, sample_waypoints,
    ):
        """REQ-EXEC-010: Returns mission_complete when no more waypoints."""
        mock_connector.latest_telemetry = make_telemetry()
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        executor.waypoints = sample_waypoints
        executor.current_waypoint_idx = len(sample_waypoints)

        result = await executor.do_log()
        assert result == "mission_complete"


@pytest.mark.unit
class TestDoRTLAndAbort:
    """Test RTL and ABORT state handlers."""

    @pytest.mark.asyncio
    async def test_rtl_calls_flight_rtl(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-EXEC-011: do_rtl calls flight.rtl() and waits for landing."""
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        result = await executor.do_rtl()
        mock_flight.rtl.assert_called_once()
        mock_flight.wait_for_landed.assert_called_once()
        assert result == "touchdown"

    @pytest.mark.asyncio
    async def test_abort_returns_abort_rtl(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-EXEC-012: do_abort returns 'abort_rtl'."""
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        result = await executor.do_abort()
        assert result == "abort_rtl"

    @pytest.mark.asyncio
    async def test_abort_stops_offboard_if_active(
        self, mock_connector, mock_flight, mock_detector,
        mock_tracker, mock_geotagger, mock_camera,
        mock_safety, default_config,
    ):
        """REQ-EXEC-012: Abort stops offboard mode when active."""
        mock_flight.is_offboard_active = True
        executor = _create_executor(
            mock_connector, mock_flight, mock_detector, mock_tracker,
            mock_geotagger, mock_camera, mock_safety, default_config,
        )
        result = await executor.do_abort()
        mock_flight.stop_offboard.assert_called_once()
        assert result == "abort_rtl"
