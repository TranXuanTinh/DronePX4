"""Unit tests for ByteTrack tracker.

Only depends on numpy (no mavsdk or ultralytics needed).
"""

import pytest
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.perception.tracker import ByteTrackWrapper, Track


class _FakeDetection:
    """Minimal detection object matching the interface ByteTrackWrapper expects."""
    def __init__(self, x1, y1, x2, y2, cls_id=0, cls_name="car", conf=0.9):
        self.bbox = np.array([x1, y1, x2, y2])
        self.class_id = cls_id
        self.class_name = cls_name
        self.confidence = conf


class TestByteTrackWrapper:
    """Test multi-object tracking."""

    @pytest.fixture
    def tracker(self):
        return ByteTrackWrapper(
            track_thresh=0.5, match_thresh=0.8, track_buffer=5, frame_rate=10,
        )

    def test_no_detections_no_tracks(self, tracker):
        tracks = tracker.update([])
        assert tracks == []

    def test_single_detection_creates_track(self, tracker):
        dets = [_FakeDetection(100, 100, 200, 200)]
        tracks = tracker.update(dets)
        assert len(tracks) == 1
        assert tracks[0].class_name == "car"
        assert tracks[0].track_id == 1

    def test_persistent_track_id(self, tracker):
        dets = [_FakeDetection(100, 100, 200, 200)]
        tracks1 = tracker.update(dets)
        tracks2 = tracker.update(dets)
        assert len(tracks1) == 1
        assert len(tracks2) == 1
        assert tracks1[0].track_id == tracks2[0].track_id

    def test_track_age_increments(self, tracker):
        dets = [_FakeDetection(100, 100, 200, 200)]
        tracker.update(dets)
        tracks = tracker.update(dets)
        assert tracks[0].age == 2

    def test_multiple_objects_tracked(self, tracker):
        dets = [
            _FakeDetection(100, 100, 200, 200, cls_name="car"),
            _FakeDetection(400, 400, 500, 500, cls_name="person"),
        ]
        tracks = tracker.update(dets)
        assert len(tracks) == 2
        ids = {t.track_id for t in tracks}
        assert len(ids) == 2

    def test_low_confidence_not_tracked(self, tracker):
        dets = [_FakeDetection(100, 100, 200, 200, conf=0.3)]
        tracks = tracker.update(dets)
        assert len(tracks) == 0

    def test_track_is_confirmed_after_3_frames(self, tracker):
        dets = [_FakeDetection(100, 100, 200, 200)]
        tracker.update(dets)
        tracker.update(dets)
        tracks = tracker.update(dets)
        assert tracks[0].is_confirmed is True

    def test_track_lost_after_buffer(self, tracker):
        dets = [_FakeDetection(100, 100, 200, 200)]
        tracker.update(dets)
        for _ in range(6):
            tracker.update([])
        dets2 = [_FakeDetection(100, 100, 200, 200)]
        tracks = tracker.update(dets2)
        assert len(tracks) == 1
        assert tracks[0].track_id != 1

    def test_reset_clears_all(self, tracker):
        tracker.update([_FakeDetection(100, 100, 200, 200)])
        tracker.reset()
        tracks = tracker.update([_FakeDetection(100, 100, 200, 200)])
        assert tracks[0].track_id == 1


class TestTrackCenter:
    def test_center(self):
        t = Track(
            track_id=1, bbox=np.array([100, 100, 200, 200]),
            class_id=0, class_name="car", confidence=0.9,
            age=1, is_confirmed=False,
        )
        assert t.center == (150, 150)


class TestIoUComputation:
    def test_identical_boxes_iou_one(self):
        boxes = np.array([[100, 100, 200, 200]])
        iou = ByteTrackWrapper._compute_iou(boxes, boxes)
        assert iou[0, 0] == pytest.approx(1.0, abs=0.001)

    def test_no_overlap_iou_zero(self):
        a = np.array([[0, 0, 10, 10]])
        b = np.array([[100, 100, 200, 200]])
        iou = ByteTrackWrapper._compute_iou(a, b)
        assert iou[0, 0] == pytest.approx(0.0, abs=0.001)

    def test_partial_overlap(self):
        a = np.array([[0, 0, 100, 100]])
        b = np.array([[50, 50, 150, 150]])
        iou = ByteTrackWrapper._compute_iou(a, b)
        expected = 2500 / 17500
        assert iou[0, 0] == pytest.approx(expected, abs=0.01)
