"""
Camera sources — CameraSource implementations (LSP-compliant).

Splits the old monolithic GazeboCamera into proper subclasses:
- GstreamerCamera: Gazebo GStreamer pipeline
- VideoFileCamera: Video file playback
- TestPatternCamera: Synthetic frames for development
- CameraFactory: Factory method for config-driven creation
"""
from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from src.core.interfaces import CameraSource

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Concrete Implementations
# ──────────────────────────────────────────────────────────────

class GstreamerCamera(CameraSource):
    """Captures frames from Gazebo via GStreamer pipeline."""

    def __init__(self, width: int = 640, height: int = 480) -> None:
        self._width = width
        self._height = height
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_count = 0

    def open(self) -> bool:
        pipeline = (
            f"udpsrc port=5600 "
            f"! application/x-rtp,encoding-name=H264 "
            f"! rtph264depay ! avdec_h264 "
            f"! videoconvert ! video/x-raw,format=BGR "
            f"! appsink drop=1"
        )
        self._cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if self._cap.isOpened():
            logger.info("Gazebo camera opened via GStreamer")
            return True
        logger.warning("GStreamer pipeline failed to open")
        self._cap = None
        return False

    def get_frame(self) -> Optional[np.ndarray]:
        if self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret:
                self._frame_count += 1
                return frame
        return None

    def release(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("GStreamer camera released")

    @property
    def frame_count(self) -> int:
        return self._frame_count


class VideoFileCamera(CameraSource):
    """Captures frames from a video file (for testing)."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_count = 0

    def open(self) -> bool:
        self._cap = cv2.VideoCapture(self._path)
        if self._cap.isOpened():
            logger.info(f"Opened video file: {self._path}")
            return True
        logger.error(f"Failed to open video: {self._path}")
        return False

    def get_frame(self) -> Optional[np.ndarray]:
        if self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret:
                self._frame_count += 1
                return frame
            # Loop video
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        return None

    def release(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("Video file camera released")

    @property
    def frame_count(self) -> int:
        return self._frame_count


class TestPatternCamera(CameraSource):
    """Generates synthetic test frames for development without Gazebo.

    Creates frames with gradient background and colored rectangles
    that simulate detectable objects.
    """

    def __init__(self, width: int = 640, height: int = 480) -> None:
        self._width = width
        self._height = height
        self._frame_count = 0
        self._opened = False

    def open(self) -> bool:
        self._opened = True
        logger.info(
            f"Test pattern camera opened ({self._width}x{self._height})"
        )
        return True

    def get_frame(self) -> Optional[np.ndarray]:
        if not self._opened:
            return None
        return self._generate_test_frame()

    def release(self) -> None:
        self._opened = False
        logger.info("Test pattern camera released")

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def _generate_test_frame(self) -> np.ndarray:
        """Generate a synthetic test frame."""
        frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)

        # Gradient background (green terrain)
        for y in range(self._height):
            green = int(60 + (y / self._height) * 80)
            frame[y, :] = [30, green, 20]

        # Simulated objects at fixed positions
        objects = [
            ((100, 150, 180, 230), (0, 0, 200), "car"),
            ((300, 200, 380, 280), (200, 200, 0), "person"),
            ((450, 100, 530, 180), (0, 200, 200), "truck"),
        ]

        # Add slight movement based on frame count
        offset_x = int(10 * np.sin(self._frame_count * 0.05))
        offset_y = int(5 * np.cos(self._frame_count * 0.03))

        for (x1, y1, x2, y2), color, label in objects:
            x1 = max(0, x1 + offset_x)
            y1 = max(0, y1 + offset_y)
            x2 = min(self._width, x2 + offset_x)
            y2 = min(self._height, y2 + offset_y)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
            cv2.putText(
                frame, label, (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
            )

        # Frame counter
        cv2.putText(
            frame,
            f"SIM Frame #{self._frame_count}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
        )

        self._frame_count += 1
        return frame


# ──────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────

class CameraFactory:
    """Factory for creating camera sources from configuration.

    Eliminates the if/elif/else chain that violated LSP in the
    old GazeboCamera class.
    """

    @staticmethod
    def create(source: str = "gazebo", **kwargs) -> CameraSource:
        """Create a camera source based on configuration.

        Args:
            source: Camera source type — "gazebo", a video file path,
                    or "test" for synthetic frames.
            **kwargs: Additional arguments (width, height, etc.)

        Returns:
            A CameraSource implementation.
        """
        width = kwargs.get("width", 640)
        height = kwargs.get("height", 480)

        if source == "gazebo":
            cam = GstreamerCamera(width=width, height=height)
            if cam.open():
                return cam
            # Fallback to test pattern if GStreamer fails
            logger.warning("Falling back to test pattern camera")
            fallback = TestPatternCamera(width=width, height=height)
            fallback.open()
            return fallback

        if source.endswith((".mp4", ".avi", ".mkv")):
            return VideoFileCamera(path=source)

        if source == "test":
            return TestPatternCamera(width=width, height=height)

        logger.warning(f"Unknown source '{source}', using test pattern")
        return TestPatternCamera(width=width, height=height)


# ──────────────────────────────────────────────────────────────
# Backward Compatibility Alias
# ──────────────────────────────────────────────────────────────

# Old code used `GazeboCamera(source="gazebo")`. Keep it working.
GazeboCamera = CameraFactory.create
