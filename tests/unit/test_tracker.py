"""
Unit tests for ByteTrackWrapper — ObjectTracker implementation.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.types import Detection, Track
from src.perception.tracker import ByteTrackWrapper


def _make_detection(x1, y1, x2, y2, conf=0.9, cls_id=0, cls_name="car"):
    return Detection(
        bbox=np.array([x1, y1, x2, y2]),
        class_id=cls_id,
        class_name=cls_name,
        confidence=conf,
    )


class TestByteTrackWrapper:
    """Test ByteTrack tracker behavior."""

    def test_no_detections_no_tracks(self, tracker=None):
        tracker = tracker or ByteTrackWrapper(track_thresh=0.5)
        tracks = tracker.update([])
        assert len(tracks) == 0

    def test_single_detection_creates_track(self, tracker=None):
        tracker = tracker or ByteTrackWrapper(track_thresh=0.5)
        det = _make_detection(100, 100, 200, 200)
        tracks = tracker.update([det])
        assert len(tracks) == 1
        assert tracks[0].track_id == 1

    def test_persistent_track_id(self, tracker=None):
        tracker = tracker or ByteTrackWrapper(track_thresh=0.5, match_thresh=0.8)
        det = _make_detection(100, 100, 200, 200)
        tracks1 = tracker.update([det])
        det2 = _make_detection(105, 105, 205, 205)
        tracks2 = tracker.update([det2])
        assert tracks1[0].track_id == tracks2[0].track_id

    def test_multiple_objects_tracked(self, tracker=None):
        tracker = tracker or ByteTrackWrapper(track_thresh=0.5)
        dets = [
            _make_detection(10, 10, 50, 50),
            _make_detection(200, 200, 300, 300),
        ]
        tracks = tracker.update(dets)
        assert len(tracks) == 2
        ids = {t.track_id for t in tracks}
        assert len(ids) == 2

    def test_low_confidence_not_tracked(self, tracker=None):
        tracker = tracker or ByteTrackWrapper(track_thresh=0.5)
        det = _make_detection(100, 100, 200, 200, conf=0.1)
        tracks = tracker.update([det])
        assert len(tracks) == 0

    def test_track_age_increments(self, tracker=None):
        tracker = tracker or ByteTrackWrapper(track_thresh=0.5, match_thresh=0.8)
        det = _make_detection(100, 100, 200, 200)
        tracker.update([det])
        tracks = tracker.update([_make_detection(105, 105, 205, 205)])
        assert tracks[0].age == 2

    def test_track_is_confirmed_after_3_frames(self, tracker=None):
        tracker = tracker or ByteTrackWrapper(track_thresh=0.5, match_thresh=0.8)
        for i in range(3):
            tracks = tracker.update([_make_detection(100 + i, 100, 200 + i, 200)])
        assert tracks[0].is_confirmed is True

    def test_track_lost_after_buffer(self, tracker=None):
        tracker = tracker or ByteTrackWrapper(track_thresh=0.5, track_buffer=2)
        tracker.update([_make_detection(100, 100, 200, 200)])
        tracker.update([])
        tracker.update([])
        tracks = tracker.update([])
        assert len(tracks) == 0

    def test_reset_clears_all(self, tracker=None):
        tracker = tracker or ByteTrackWrapper(track_thresh=0.5)
        tracker.update([_make_detection(100, 100, 200, 200)])
        tracker.reset()
        tracks = tracker.update([_make_detection(100, 100, 200, 200)])
        assert tracks[0].track_id == 1  # IDs restart


class TestTrackCenter:
    def test_center(self):
        t = Track(
            track_id=1,
            bbox=np.array([10, 20, 30, 40]),
            class_id=0, class_name="car",
            confidence=0.9, age=1, is_confirmed=True,
        )
        assert t.center == (20, 30)


class TestIoUComputation:
    def test_identical_boxes_iou_one(self):
        a = np.array([[0, 0, 10, 10]])
        b = np.array([[0, 0, 10, 10]])
        iou = ByteTrackWrapper._compute_iou(a, b)
        assert abs(iou[0, 0] - 1.0) < 1e-4

    def test_no_overlap_iou_zero(self):
        a = np.array([[0, 0, 10, 10]])
        b = np.array([[20, 20, 30, 30]])
        iou = ByteTrackWrapper._compute_iou(a, b)
        assert iou[0, 0] < 1e-4

    def test_partial_overlap(self):
        a = np.array([[0, 0, 10, 10]])
        b = np.array([[5, 5, 15, 15]])
        iou = ByteTrackWrapper._compute_iou(a, b)
        assert 0.0 < iou[0, 0] < 1.0
