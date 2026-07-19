"""
Unit tests for simulated detections fallback with TestPatternCamera.
"""
from unittest.mock import MagicMock, AsyncMock
import numpy as np
import pytest

from src.core.types import Detection, TracksUpdatedEvent
from src.perception.camera import TestPatternCamera
from src.mission.executor import MissionExecutor



def test_test_pattern_camera_simulated_detections():
    """Verify TestPatternCamera returns correct simulated detections matching generated frames."""
    camera = TestPatternCamera(640, 480)
    assert camera.open() is True
    
    # Generate first frame
    frame = camera.get_frame()
    assert frame is not None
    assert frame.shape == (480, 640, 3)
    
    # Get detections for the frame
    detections = camera.get_detections()
    assert len(detections) == 3
    
    classes = [d.class_name for d in detections]
    assert "car" in classes
    assert "person" in classes
    assert "truck" in classes
    
    for det in detections:
        assert isinstance(det, Detection)
        assert det.confidence == 0.92
        assert len(det.bbox) == 4
        # Bboxes must be within frame boundaries
        assert 0 <= det.bbox[0] <= 640
        assert 0 <= det.bbox[1] <= 480
        assert 0 <= det.bbox[2] <= 640
        assert 0 <= det.bbox[3] <= 480


@pytest.mark.asyncio
async def test_mission_executor_uses_simulated_detections(
    mock_connector, mock_flight, mock_detector, mock_tracker, mock_geotagger, mock_safety, default_config, sample_waypoints
):
    """Verify MissionExecutor do_search uses get_detections if available on camera."""
    camera = TestPatternCamera(640, 480)
    camera.open()
    
    event_bus = AsyncMock()
    
    executor = MissionExecutor(
        connector=mock_connector,
        flight=mock_flight,
        detector=mock_detector,
        tracker=mock_tracker,
        geotagger=mock_geotagger,
        camera=camera,
        safety=mock_safety,
        config=default_config,
        event_bus=event_bus,
    )
    
    executor.waypoints = sample_waypoints
    executor.current_waypoint_idx = 0
    
    # Setup mock tracker update and geotagger tag_detections
    mock_tracker.update = MagicMock(return_value=[])
    
    # Execute do_search state step
    await executor.do_search()
    
    # Check that YOLODetector detect was called (always run to maintain GPU/CUDA activity)
    mock_detector.detect.assert_called_once()
    
    # Check that tracker.update was called with the simulated detections from camera
    mock_tracker.update.assert_called_once()
    passed_args = mock_tracker.update.call_args[0][0]
    assert len(passed_args) == 3
    assert passed_args[0].class_name in ["car", "person", "truck"]
    
    # Check that EventBus.publish was called with TracksUpdatedEvent
    event_bus.publish.assert_called_once()
    published_event = event_bus.publish.call_args[0][0]
    assert isinstance(published_event, TracksUpdatedEvent)


@pytest.mark.asyncio
async def test_do_search_filters_duplicate_detections(
    mock_connector, mock_flight, mock_detector, mock_tracker, mock_geotagger, mock_safety, default_config, sample_waypoints, sample_geotagged_detection
):
    """Verify that do_search filters out detections within 10 meters of already logged ones."""
    camera = TestPatternCamera(640, 480)
    camera.open()
    
    event_bus = AsyncMock()
    
    executor = MissionExecutor(
        connector=mock_connector,
        flight=mock_flight,
        detector=mock_detector,
        tracker=mock_tracker,
        geotagger=mock_geotagger,
        camera=camera,
        safety=mock_safety,
        config=default_config,
        event_bus=event_bus,
    )
    
    executor.waypoints = sample_waypoints
    executor.current_waypoint_idx = 0
    
    # 1. First run: no logged detections, should find detections and return "object_detected"
    mock_geotagger.tag_detections = MagicMock(return_value=[sample_geotagged_detection])
    
    # Simulate confirmed track in tracker
    mock_track = MagicMock()
    mock_track.is_confirmed = True
    mock_tracker.update = MagicMock(return_value=[mock_track])
    
    res = await executor.do_search()
    assert res == "object_detected"
    assert executor.pending_detection == sample_geotagged_detection
    
    # 2. Simulate logging of this detection
    executor.detections.append(sample_geotagged_detection)
    executor.pending_detection = None
    
    # 3. Second run: same detection returned by geotagger. It should be filtered out.
    res = await executor.do_search()
    assert res is None  # Should not trigger "object_detected" again
    assert executor.pending_detection is None

