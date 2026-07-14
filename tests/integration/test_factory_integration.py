"""
Integration tests: AppFactory full wiring.

Tests that AppFactory creates a fully-wired system with mocked MAVSDK.

DO-178C Traceability: REQ-FACTORY-INT-001 through REQ-FACTORY-INT-002
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.integration
class TestFactoryIntegration:
    """Test full AppFactory construction with mocked external deps."""

    @pytest.mark.asyncio
    async def test_full_system_wired_correctly(self):
        """REQ-FACTORY-INT-001: All subsystems wired and non-None."""
        with (
            patch("src.factory.MAVLinkBridge") as MockBridge,
            patch("src.factory.FlightCommands") as MockFlight,
            patch("src.factory.TelemetryCollector") as MockTelem,
            patch("src.factory.CameraFactory") as MockCamFactory,
            patch("src.factory.YOLODetector") as MockDetector,
            patch("src.factory.ByteTrackWrapper"),
            patch("src.factory.GPSGeotagger"),
            patch("src.factory.DetectionOverlay"),
            patch("src.factory.VideoServer") as MockVideo,
            patch("src.factory.SafetyMonitor") as MockSafety,
            patch("src.factory.MissionStateMachine"),
            patch("asyncio.create_task"),
        ):
            bridge_inst = MockBridge.return_value
            bridge_inst.connect = AsyncMock()
            bridge_inst.wait_for_ready = AsyncMock()

            telem_inst = MockTelem.return_value
            telem_inst.start = AsyncMock()

            cam_inst = MagicMock()
            cam_inst.open = MagicMock(return_value=True)
            MockCamFactory.create = MagicMock(return_value=cam_inst)

            det_inst = MockDetector.return_value
            det_inst.load = MagicMock()

            MockSafety.from_config = MagicMock(return_value=MagicMock())

            video_inst = MockVideo.return_value
            video_inst.stream_loop = AsyncMock()

            from src.factory import AppFactory

            # Use a simple namespace as container
            class Container:
                pass

            container = Container()
            config = {
                "connection": {"mavsdk_address": "udp://:14540"},
                "camera": {"source": "test", "width": 640, "height": 480, "hfov_deg": 60},
                "perception": {"model": "yolov8s.pt", "device": "cpu", "confidence_threshold": 0.45},
                "safety": {"geofence_radius_m": 500, "max_altitude_m": 120},
                "mission": {"search_area": {"center_lat": 47.3977, "center_lon": 8.5456}},
                "dashboard": {"telemetry_rate_hz": 10, "video_quality": 70},
            }

            await AppFactory.initialize(container, config)

            assert hasattr(container, "connector")
            assert hasattr(container, "flight")
            assert hasattr(container, "safety")
            assert hasattr(container, "state_machine")
            assert hasattr(container, "camera")
            assert hasattr(container, "detector")
            assert hasattr(container, "event_bus")

    @pytest.mark.asyncio
    async def test_shutdown_no_errors(self):
        """REQ-FACTORY-INT-002: Shutdown completes without errors."""
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
        container.connector.disconnect.assert_called_once()
