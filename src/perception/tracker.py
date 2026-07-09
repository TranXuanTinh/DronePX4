"""
Tracker — ByteTrack multi-object tracking wrapper.

Provides persistent track IDs across frames for detected objects.
Lightweight and fast — no ReID network needed.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """A tracked object with persistent ID."""
    track_id: int
    bbox: np.ndarray         # [x1, y1, x2, y2]
    class_id: int
    class_name: str
    confidence: float
    age: int                 # Number of frames this track has existed
    is_confirmed: bool       # Whether track has enough history

    @property
    def center(self) -> tuple[int, int]:
        return (
            int((self.bbox[0] + self.bbox[2]) / 2),
            int((self.bbox[1] + self.bbox[3]) / 2),
        )


class ByteTrackWrapper:
    """Multi-object tracker using a simplified ByteTrack-style algorithm.

    ByteTrack associates detections to tracks using IoU matching
    in two rounds: high-confidence matches first, then low-confidence.

    For simulation, we use a simplified implementation. For production,
    swap with the full ByteTrack library.
    """

    def __init__(
        self,
        track_thresh: float = 0.5,
        match_thresh: float = 0.8,
        track_buffer: int = 30,
        frame_rate: int = 10,
    ):
        self._track_thresh = track_thresh
        self._match_thresh = match_thresh
        self._track_buffer = track_buffer
        self._frame_rate = frame_rate

        self._tracks: dict[int, _TrackState] = {}
        self._next_id = 1
        self._frame_count = 0

    def update(self, detections: list) -> List[Track]:
        """Update tracks with new detections.

        Args:
            detections: List of Detection objects from the detector.

        Returns:
            List of active Track objects with persistent IDs.
        """
        self._frame_count += 1

        if not detections:
            # Age out existing tracks
            self._age_tracks()
            return self._get_active_tracks()

        # Build detection matrix: [N, 5] = [x1, y1, x2, y2, score]
        det_bboxes = np.array([d.bbox for d in detections])
        det_scores = np.array([d.confidence for d in detections])

        # Match detections to existing tracks using IoU
        matched, unmatched_dets, unmatched_tracks = self._match(
            det_bboxes, det_scores
        )

        # Update matched tracks
        for track_idx, det_idx in matched:
            track_id = list(self._tracks.keys())[track_idx]
            det = detections[det_idx]
            self._tracks[track_id].update(det.bbox, det.confidence, det.class_id, det.class_name)

        # Create new tracks for unmatched detections
        for det_idx in unmatched_dets:
            det = detections[det_idx]
            if det.confidence >= self._track_thresh:
                self._tracks[self._next_id] = _TrackState(
                    track_id=self._next_id,
                    bbox=det.bbox,
                    confidence=det.confidence,
                    class_id=det.class_id,
                    class_name=det.class_name,
                )
                self._next_id += 1

        # Age unmatched tracks
        for track_idx in unmatched_tracks:
            track_id = list(self._tracks.keys())[track_idx]
            self._tracks[track_id].miss()

        # Remove dead tracks
        self._remove_dead_tracks()

        return self._get_active_tracks()

    def _match(self, det_bboxes, det_scores):
        """Match detections to existing tracks using IoU."""
        if not self._tracks or len(det_bboxes) == 0:
            unmatched_dets = list(range(len(det_bboxes)))
            return [], unmatched_dets, []

        track_bboxes = np.array([t.bbox for t in self._tracks.values()])

        # Compute IoU matrix
        iou_matrix = self._compute_iou(track_bboxes, det_bboxes)

        matched = []
        unmatched_dets = list(range(len(det_bboxes)))
        unmatched_tracks = list(range(len(track_bboxes)))

        # Greedy matching (simplified; production uses Hungarian algorithm)
        while True:
            if iou_matrix.size == 0:
                break
            max_iou = iou_matrix.max()
            if max_iou < (1.0 - self._match_thresh):
                break

            track_idx, det_idx = np.unravel_index(
                iou_matrix.argmax(), iou_matrix.shape
            )

            matched.append((track_idx, det_idx))

            if track_idx in unmatched_tracks:
                unmatched_tracks.remove(track_idx)
            if det_idx in unmatched_dets:
                unmatched_dets.remove(det_idx)

            iou_matrix[track_idx, :] = 0
            iou_matrix[:, det_idx] = 0

        return matched, unmatched_dets, unmatched_tracks

    @staticmethod
    def _compute_iou(boxes_a: np.ndarray, boxes_b: np.ndarray) -> np.ndarray:
        """Compute IoU between two sets of bboxes. Shape: (N, M)."""
        x1 = np.maximum(boxes_a[:, 0:1], boxes_b[:, 0].T)
        y1 = np.maximum(boxes_a[:, 1:2], boxes_b[:, 1].T)
        x2 = np.minimum(boxes_a[:, 2:3], boxes_b[:, 2].T)
        y2 = np.minimum(boxes_a[:, 3:4], boxes_b[:, 3].T)

        intersection = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)

        area_a = (boxes_a[:, 2] - boxes_a[:, 0]) * (boxes_a[:, 3] - boxes_a[:, 1])
        area_b = (boxes_b[:, 2] - boxes_b[:, 0]) * (boxes_b[:, 3] - boxes_b[:, 1])

        union = area_a[:, None] + area_b[None, :] - intersection

        return intersection / (union + 1e-6)

    def _age_tracks(self):
        """Increment miss count for all tracks."""
        for track in self._tracks.values():
            track.miss()
        self._remove_dead_tracks()

    def _remove_dead_tracks(self):
        """Remove tracks that haven't been updated recently."""
        dead_ids = [
            tid for tid, t in self._tracks.items()
            if t.miss_count > self._track_buffer
        ]
        for tid in dead_ids:
            del self._tracks[tid]

    def _get_active_tracks(self) -> List[Track]:
        """Get list of currently active tracks."""
        return [
            Track(
                track_id=t.track_id,
                bbox=t.bbox.copy(),
                class_id=t.class_id,
                class_name=t.class_name,
                confidence=t.confidence,
                age=t.age,
                is_confirmed=t.age >= 3,
            )
            for t in self._tracks.values()
            if t.miss_count == 0  # Only return tracks updated this frame
        ]

    def reset(self):
        """Clear all tracks."""
        self._tracks.clear()
        self._next_id = 1
        self._frame_count = 0


class _TrackState:
    """Internal track state (not exposed to consumers)."""

    def __init__(
        self, track_id: int, bbox: np.ndarray,
        confidence: float, class_id: int, class_name: str
    ):
        self.track_id = track_id
        self.bbox = bbox.copy()
        self.confidence = confidence
        self.class_id = class_id
        self.class_name = class_name
        self.age = 1
        self.miss_count = 0

    def update(self, bbox: np.ndarray, confidence: float,
               class_id: int, class_name: str):
        """Update track with new detection."""
        self.bbox = bbox.copy()
        self.confidence = confidence
        self.class_id = class_id
        self.class_name = class_name
        self.age += 1
        self.miss_count = 0

    def miss(self):
        """Track was not matched in this frame."""
        self.miss_count += 1
