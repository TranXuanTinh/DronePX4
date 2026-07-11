"""
Overlay — Detection overlay renderer for video frames.

Draws bounding boxes, class labels, track IDs, and confidence
scores onto video frames for the dashboard display.
"""

import cv2
import numpy as np
from typing import List

from src.core.types import Track


# Color palette for different classes (BGR format)
CLASS_COLORS = {
    "person":    (0, 200, 0),      # Green
    "car":       (255, 140, 0),    # Orange
    "truck":     (0, 100, 255),    # Red-Orange
    "bicycle":   (255, 255, 0),    # Cyan
    "backpack":  (200, 0, 200),    # Purple
    "vehicle":   (255, 165, 0),    # Orange
    "damage":    (0, 0, 255),      # Red
    "equipment": (255, 255, 0),    # Cyan
    "debris":    (128, 0, 128),    # Purple
}

DEFAULT_COLOR = (200, 200, 200)  # Light gray


class DetectionOverlay:
    """Renders detection boxes, labels, and track IDs onto frames."""

    def __init__(self, line_thickness: int = 2, font_scale: float = 0.6):
        self._thickness = line_thickness
        self._font_scale = font_scale
        self._font = cv2.FONT_HERSHEY_SIMPLEX

    def draw(
        self,
        frame: np.ndarray,
        tracks: List[Track],
        show_ids: bool = True,
        show_confidence: bool = True,
    ) -> np.ndarray:
        """Draw detection overlays on a frame.

        Args:
            frame: Input BGR frame (will be modified in-place)
            tracks: List of Track objects to draw
            show_ids: Whether to show track IDs
            show_confidence: Whether to show confidence scores

        Returns:
            Frame with overlays drawn
        """
        for track in tracks:
            x1, y1, x2, y2 = track.bbox.astype(int)
            color = CLASS_COLORS.get(track.class_name, DEFAULT_COLOR)

            # Bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, self._thickness)

            # Label background
            label_parts = []
            if show_ids:
                label_parts.append(f"#{track.track_id}")
            label_parts.append(track.class_name)
            if show_confidence:
                label_parts.append(f"{track.confidence:.0%}")

            label = " ".join(label_parts)

            (label_w, label_h), baseline = cv2.getTextSize(
                label, self._font, self._font_scale, 1
            )

            # Draw label background
            cv2.rectangle(
                frame,
                (x1, y1 - label_h - baseline - 4),
                (x1 + label_w + 4, y1),
                color,
                -1,  # Filled
            )

            # Draw label text
            cv2.putText(
                frame,
                label,
                (x1 + 2, y1 - baseline - 2),
                self._font,
                self._font_scale,
                (255, 255, 255),  # White text
                1,
                cv2.LINE_AA,
            )

            # Center dot
            cx, cy = track.center
            cv2.circle(frame, (cx, cy), 3, color, -1)

        # Detection count overlay
        if tracks:
            count_text = f"Detections: {len(tracks)}"
            cv2.putText(
                frame,
                count_text,
                (10, frame.shape[0] - 10),
                self._font,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        return frame

    def draw_status(
        self,
        frame: np.ndarray,
        state: str,
        battery_pct: float,
        altitude_m: float,
        fps: float,
    ) -> np.ndarray:
        """Draw status information overlay on frame.

        Args:
            frame: Input frame
            state: Current mission state
            battery_pct: Battery percentage
            altitude_m: Current altitude
            fps: Processing FPS

        Returns:
            Frame with status overlay
        """
        h, w = frame.shape[:2]

        # Semi-transparent status bar at top
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 30), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # Status text
        status = (
            f"State: {state} | "
            f"Battery: {battery_pct:.0f}% | "
            f"Alt: {altitude_m:.1f}m | "
            f"FPS: {fps:.1f}"
        )
        cv2.putText(
            frame, status, (10, 20),
            self._font, 0.45, (255, 255, 255), 1, cv2.LINE_AA,
        )

        return frame
