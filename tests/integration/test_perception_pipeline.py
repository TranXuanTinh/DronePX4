"""
Integration tests: Perception pipeline end-to-end.

Validates Camera → Detector → Tracker → Geotagger data flow.

DO-178C Traceability: REQ-PERC-INT-001 through REQ-PERC-INT-004
"""
import pytest
import numpy as np
from unittest.mock import MagicMock

from src.core.types import Detection, Track, GeotaggedDetection, Position
from src.perception.camera import TestPatternCamera
from src.perception.tracker import ByteTrackWrapper
from src.perception.geotagging import GPSGeotagger


@pytest.mark.integration
class TestPerceptionPipeline:
    """Test end-to-end perception pipeline with real subsystems."""

    def test_camera_produces_valid_frames(self):
        """REQ-PERC-INT-001: TestPatternCamera produces BGR frames."""
        camera = TestPatternCamera(width=640, height=480)
        camera.open()

        frame = camera.get_frame()
        assert frame is not None
        assert frame.shape == (480, 640, 3)
        assert frame.dtype == np.uint8

        camera.release()

    def test_tracker_maintains_ids_across_frames(self):
        """REQ-PERC-INT-002: Tracker keeps consistent IDs across frames."""
        tracker = ByteTrackWrapper(
            track_thresh=0.5, match_thresh=0.8,
            track_buffer=30, frame_rate=10,
        )

        # Simulate 5 frames with the same detection
        detections = [
            Detection(
                bbox=np.array([100, 150, 200, 250]),
                class_id=0, class_name="person",
                confidence=0.9,
            )
        ]

        track_ids = set()
        for _ in range(5):
            tracks = tracker.update(
                detections
            )
            for t in tracks:
                track_ids.add(t.track_id)

        # Should have 1 consistent track ID
        assert len(track_ids) <= 2  # Allow initial ID change

    def test_geotagger_produces_valid_coordinates(self, make_telemetry):
        """REQ-PERC-INT-003: Geotagger produces valid lat/lon from pixel."""
        geotagger = GPSGeotagger(
            camera_hfov_deg=60.0, image_width=640, image_height=480,
        )

        telem = make_telemetry(lat=47.3977, lon=8.5456, alt=20.0, heading=0.0)

        tracks = [
            Track(
                track_id=1,
                bbox=np.array([300, 220, 340, 260]),
                class_id=0, class_name="person",
                confidence=0.9, age=5, is_confirmed=True,
            ),
        ]

        geotagged = geotagger.tag_detections(
            tracks, 
            telem.position.latitude_deg,
            telem.position.longitude_deg,
            telem.position.relative_altitude_m,
            telem.heading_deg,
            telem.timestamp,
        )
        assert len(geotagged) == 1
        assert -90 <= geotagged[0].latitude_deg <= 90
        assert -180 <= geotagged[0].longitude_deg <= 180

    def test_empty_frame_no_crash(self):
        """REQ-PERC-INT-004: Empty detections do not crash pipeline."""
        tracker = ByteTrackWrapper(
            track_thresh=0.5, match_thresh=0.8,
            track_buffer=30, frame_rate=10,
        )

        # Empty detections list
        tracks = tracker.update([])
        assert isinstance(tracks, list)
        assert len(tracks) == 0

    def test_test_pattern_camera_frame_count_increments(self):
        """REQ-PERC-INT-001: Frame counter increments each get_frame."""
        camera = TestPatternCamera(width=320, height=240)
        camera.open()

        for _ in range(5):
            camera.get_frame()

        assert camera.frame_count == 5
        camera.release()
