"""
Tracker — ByteTrack implementation of ObjectTracker.

Provides persistent track IDs across frames using a simplified
ByteTrack-style IoU matching algorithm.
"""
from __future__ import annotations

import logging
from typing import List

import numpy as np

from src.core.interfaces import ObjectTracker
from src.core.types import Detection, Track

logger = logging.getLogger(__name__)


class ByteTrackWrapper(ObjectTracker):
    """Multi-object tracker using a simplified ByteTrack-style algorithm.

    Implements the ObjectTracker interface. Associates detections to
    tracks using IoU matching in a greedy fashion.

    For production, swap with the full ByteTrack library by implementing
    the same ObjectTracker interface.
    """

    def __init__(
        self,
        track_thresh: float = 0.5,
        match_thresh: float = 0.8,
        track_buffer: int = 30,
        frame_rate: int = 10,
    ) -> None:
        self._track_thresh = track_thresh
        self._match_thresh = match_thresh
        self._track_buffer = track_buffer
        self._frame_rate = frame_rate

        self._tracks: dict[int, _TrackState] = {}
        self._next_id = 1
        self._frame_count = 0

    # ── ObjectTracker interface ──────────────────────────────

    def update(self, detections: list) -> List[Track]:
        self._frame_count += 1

        if not detections:
            self._age_tracks()
            return self._get_active_tracks()

        det_bboxes = np.array([d.bbox for d in detections])
        det_scores = np.array([d.confidence for d in detections])

        matched, unmatched_dets, unmatched_tracks = self._match(
            det_bboxes, det_scores,
        )

        # Update matched tracks
        for track_idx, det_idx in matched:
            track_id = list(self._tracks.keys())[track_idx]
            det = detections[det_idx]
            self._tracks[track_id].update(
                det.bbox, det.confidence, det.class_id, det.class_name,
            )

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

        self._remove_dead_tracks()
        return self._get_active_tracks()

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1
        self._frame_count = 0

    # ── Matching ─────────────────────────────────────────────

    def _match(self, det_bboxes, det_scores):
        """Match detections to existing tracks using IoU."""
        if not self._tracks or len(det_bboxes) == 0:
            return [], list(range(len(det_bboxes))), []

        track_bboxes = np.array([t.bbox for t in self._tracks.values()])
        iou_matrix = self._compute_iou(track_bboxes, det_bboxes)

        matched = []
        unmatched_dets = list(range(len(det_bboxes)))
        unmatched_tracks = list(range(len(track_bboxes)))

        # Greedy matching
        while True:
            if iou_matrix.size == 0:
                break
            max_iou = iou_matrix.max()
            if max_iou < (1.0 - self._match_thresh):
                break

            track_idx, det_idx = np.unravel_index(
                iou_matrix.argmax(), iou_matrix.shape,
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
    def _compute_iou(
        boxes_a: np.ndarray, boxes_b: np.ndarray,
    ) -> np.ndarray:
        """Compute IoU between two sets of bboxes. Shape: (N, M)."""
        x1 = np.maximum(boxes_a[:, 0:1], boxes_b[:, 0].T)
        y1 = np.maximum(boxes_a[:, 1:2], boxes_b[:, 1].T)
        x2 = np.minimum(boxes_a[:, 2:3], boxes_b[:, 2].T)
        y2 = np.minimum(boxes_a[:, 3:4], boxes_b[:, 3].T)

        intersection = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)

        area_a = (
            (boxes_a[:, 2] - boxes_a[:, 0])
            * (boxes_a[:, 3] - boxes_a[:, 1])
        )
        area_b = (
            (boxes_b[:, 2] - boxes_b[:, 0])
            * (boxes_b[:, 3] - boxes_b[:, 1])
        )

        union = area_a[:, None] + area_b[None, :] - intersection
        return intersection / (union + 1e-6)

    # ── Track management ─────────────────────────────────────

    def _age_tracks(self) -> None:
        for track in self._tracks.values():
            track.miss()
        self._remove_dead_tracks()

    def _remove_dead_tracks(self) -> None:
        dead_ids = [
            tid for tid, t in self._tracks.items()
            if t.miss_count > self._track_buffer
        ]
        for tid in dead_ids:
            del self._tracks[tid]

    def _get_active_tracks(self) -> List[Track]:
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
            if t.miss_count == 0
        ]


class _TrackState:
    """Internal mutable track state (not exposed to consumers)."""

    __slots__ = (
        "track_id", "bbox", "confidence", "class_id",
        "class_name", "age", "miss_count",
    )

    def __init__(
        self, track_id: int, bbox: np.ndarray,
        confidence: float, class_id: int, class_name: str,
    ) -> None:
        self.track_id = track_id
        self.bbox = bbox.copy()
        self.confidence = confidence
        self.class_id = class_id
        self.class_name = class_name
        self.age = 1
        self.miss_count = 0

    def update(
        self, bbox: np.ndarray, confidence: float,
        class_id: int, class_name: str,
    ) -> None:
        self.bbox = bbox.copy()
        self.confidence = confidence
        self.class_id = class_id
        self.class_name = class_name
        self.age += 1
        self.miss_count = 0

    def miss(self) -> None:
        self.miss_count += 1
