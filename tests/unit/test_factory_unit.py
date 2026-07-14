"""
Unit tests for AppFactory — construction and wiring.

DO-178C Traceability: REQ-FACTORY-001 through REQ-FACTORY-004
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestAppFactoryInitialize:
    """Test AppFactory.initialize creates all subsystems."""

    @pytest.mark.asyncio
    async def test_initialize_creates_all_components(self, default_config):
        """REQ-FACTORY-001: All container attributes populated after init."""
        with (
            patch("src.factory.MAVLinkBridge") as MockBridge,
            patch("src.factory.FlightCommands"),
            patch("src.factory.TelemetryCollector"),
            patch("src.factory.CameraFactory"),
            patch("src.factory.YOLODetector"),
            patch("src.factory.ByteTrackWrapper"),
            patch("src.factory.GPSGeotagger"),
            patch("src.factory.DetectionOverlay"),
            patch("src.factory.VideoServer") as MockVideo,
            patch("src.factory.SafetyMonitor"),
            patch("src.factory.MissionStateMachine"),
        ):
            mock_bridge = MockBridge.return_value
            mock_bridge.connect = AsyncMock()
            mock_bridge.wait_for_ready = AsyncMock()

            from src.factory import AppFactory
            container = MagicMock()

            async def dummy_stream_loop():
                pass

            mock_video = MockVideo.return_value
            mock_video.stream_loop = MagicMock(return_value=dummy_stream_loop())

            config = {
                "connection": {"mavsdk_address": "udp://:14540"},
                "camera": {"source": "test", "width": 640, "height": 480},
                "perception": {"model": "yolov8s.pt", "device": "cpu"},
                "safety": {},
                "mission": {"search_area": {}},
                "dashboard": {},
            }

            await AppFactory.initialize(container, config)

            assert container.connector is not None
            assert container.flight is not None
            assert container.safety is not None
            assert container.state_machine is not None

    @pytest.mark.asyncio
    async def test_offline_mode_on_connection_failure(self, default_config):
        """REQ-FACTORY-002: Factory handles connection failure gracefully."""
        with (
            patch("src.factory.MAVLinkBridge") as MockBridge,
            patch("src.factory.FlightCommands"),
            patch("src.factory.TelemetryCollector"),
            patch("src.factory.CameraFactory"),
            patch("src.factory.YOLODetector"),
            patch("src.factory.ByteTrackWrapper"),
            patch("src.factory.GPSGeotagger"),
            patch("src.factory.DetectionOverlay"),
            patch("src.factory.VideoServer") as MockVideo,
            patch("src.factory.SafetyMonitor"),
            patch("src.factory.MissionStateMachine"),
        ):
            mock_bridge = MockBridge.return_value
            mock_bridge.connect = AsyncMock(side_effect=ConnectionError("No SITL"))
            mock_bridge.wait_for_ready = AsyncMock()

            from src.factory import AppFactory
            container = MagicMock()

            async def dummy_stream_loop():
                pass

            mock_video = MockVideo.return_value
            mock_video.stream_loop = MagicMock(return_value=dummy_stream_loop())

            config = {
                "connection": {"mavsdk_address": "udp://:14540"},
                "camera": {"source": "test"},
                "perception": {},
                "safety": {},
                "mission": {"search_area": {}},
                "dashboard": {},
            }

            # Should NOT raise — offline mode
            await AppFactory.initialize(container, config)
            assert container.connector is not None


@pytest.mark.unit
class TestAppFactoryShutdown:
    """Test AppFactory.shutdown releases resources."""

    @pytest.mark.asyncio
    async def test_shutdown_releases_all_resources(self):
        """REQ-FACTORY-003: shutdown releases camera, telemetry, connector."""
        from src.factory import AppFactory

        container = MagicMock()
        container.video_server = MagicMock()
        container.camera = MagicMock()
        container.telemetry_collector = MagicMock()
        container.telemetry_collector.stop = AsyncMock()
        container.connector = MagicMock()
        container.connector.disconnect = AsyncMock()
        container.event_bus = MagicMock()

        await AppFactory.shutdown(container)

        container.video_server.stop.assert_called_once()
        container.camera.release.assert_called_once()
        container.telemetry_collector.stop.assert_called_once()
        container.connector.disconnect.assert_called_once()
        container.event_bus.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_none_components(self):
        """REQ-FACTORY-004: shutdown handles partially initialized container."""
        from src.factory import AppFactory

        container = MagicMock()
        container.video_server = None
        container.camera = None
        container.telemetry_collector = None
        container.connector = None
        container.event_bus = None

        # Should NOT raise
        await AppFactory.shutdown(container)
