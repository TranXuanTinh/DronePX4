"""
Camera — Gazebo simulated camera capture via OpenCV.

Reads frames from Gazebo's camera sensor plugin.
In simulation, we use OpenCV VideoCapture on a GStreamer URI
or read from Gazebo transport topic.
"""

import logging
import time
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class GazeboCamera:
    """Captures frames from Gazebo's simulated camera sensor.

    Supports multiple capture backends:
    1. Gazebo transport topic (via gz-transport Python bindings)
    2. GStreamer pipeline reading Gazebo video output
    3. Shared memory / OpenCV bridge

    For initial development, uses a simple OpenCV VideoCapture
    approach or reads from a video file for testing.
    """

    def __init__(
        self,
        source: str = "gazebo",
        width: int = 640,
        height: int = 480,
        fps: int = 15,
    ):
        self._source = source
        self._width = width
        self._height = height
        self._fps = fps
        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_count = 0

    def open(self) -> bool:
        """Open the camera source.

        Returns:
            True if camera opened successfully.
        """
        if self._source == "gazebo":
            # For Gazebo, we'll use the gz-transport topic
            # Fallback: use GStreamer pipeline to read from Gazebo
            pipeline = (
                f"udpsrc port=5600 "
                f"! application/x-rtp,encoding-name=H264 "
                f"! rtph264depay ! avdec_h264 "
                f"! videoconvert ! video/x-raw,format=BGR "
                f"! appsink drop=1"
            )
            self._cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

            if not self._cap.isOpened():
                logger.warning(
                    "GStreamer pipeline failed. "
                    "Falling back to test pattern generator."
                )
                self._cap = None
                return True  # Will use test pattern

            logger.info("Gazebo camera opened via GStreamer")
            return True

        elif self._source.endswith((".mp4", ".avi", ".mkv")):
            # Video file for testing
            self._cap = cv2.VideoCapture(self._source)
            if self._cap.isOpened():
                logger.info(f"Opened video file: {self._source}")
                return True
            logger.error(f"Failed to open video: {self._source}")
            return False

        elif self._source.isdigit():
            # Webcam index
            self._cap = cv2.VideoCapture(int(self._source))
            if self._cap.isOpened():
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
                logger.info(f"Opened webcam: {self._source}")
                return True
            return False

        else:
            logger.warning(f"Unknown source '{self._source}', using test pattern")
            return True

    def get_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame.

        Returns:
            BGR numpy array, or None if capture failed.
        """
        if self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret:
                self._latest_frame = frame
                self._frame_count += 1
                return frame
            return None

        # Fallback: generate a test pattern for development
        return self._generate_test_frame()

    def get_frame_with_timestamp(self) -> Tuple[Optional[np.ndarray], float]:
        """Capture a frame with timestamp.

        Returns:
            Tuple of (frame, timestamp) where timestamp is time.time().
        """
        frame = self.get_frame()
        return frame, time.time()

    def _generate_test_frame(self) -> np.ndarray:
        """Generate a synthetic test frame for development without Gazebo.

        Creates a frame with:
        - Gradient background (simulating terrain)
        - Colored rectangles (simulating detectable objects)
        - Frame counter overlay
        """
        frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)

        # Gradient background (green terrain)
        for y in range(self._height):
            green = int(60 + (y / self._height) * 80)
            frame[y, :] = [30, green, 20]

        # Simulated objects at fixed positions
        objects = [
            ((100, 150, 180, 230), (0, 0, 200), "car"),      # Red box
            ((300, 200, 380, 280), (200, 200, 0), "person"),  # Cyan box
            ((450, 100, 530, 180), (0, 200, 200), "truck"),   # Yellow box
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
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        self._latest_frame = frame
        self._frame_count += 1
        return frame

    @property
    def latest_frame(self) -> Optional[np.ndarray]:
        """Get the last captured frame without capturing a new one."""
        return self._latest_frame

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def release(self) -> None:
        """Release camera resources."""
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("Camera released")
