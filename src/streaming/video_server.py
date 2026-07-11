"""
Video Server — WebSocket MJPEG streaming for simulation dashboard.

Streams Gazebo camera frames (with detection overlays) as MJPEG
over WebSocket connections. Simple and effective for simulation —
no GStreamer or WebRTC complexity needed.
"""

import asyncio
import logging
import time
from typing import List, Optional, Set

import cv2
import numpy as np

from src.core.interfaces import CameraSource
from src.core.types import Track
from src.streaming.overlay import DetectionOverlay

logger = logging.getLogger(__name__)


class VideoServer:
    """WebSocket MJPEG video streamer for simulation.

    Captures frames from Gazebo camera, draws detection overlays,
    encodes as JPEG, and sends to all connected WebSocket clients.
    """

    def __init__(
        self,
        camera: CameraSource,
        overlay: DetectionOverlay,
        jpeg_quality: int = 70,
        target_fps: float = 15.0,
    ):
        self._camera = camera
        self._overlay = overlay
        self._jpeg_quality = jpeg_quality
        self._target_fps = target_fps
        self._frame_interval = 1.0 / target_fps

        self._clients: Set = set()
        self._current_tracks: List[Track] = []
        self._mission_state: str = "IDLE"
        self._battery_pct: float = 100.0
        self._altitude_m: float = 0.0
        self._running = False
        self._fps_counter = _FPSCounter()

    def update_tracks(self, tracks: List[Track]) -> None:
        """Update current detection tracks for overlay rendering."""
        self._current_tracks = tracks

    def update_status(
        self, state: str, battery_pct: float, altitude_m: float
    ) -> None:
        """Update status bar information."""
        self._mission_state = state
        self._battery_pct = battery_pct
        self._altitude_m = altitude_m

    async def register_client(self, websocket) -> None:
        """Register a new WebSocket client."""
        self._clients.add(websocket)
        logger.info(f"Video client connected (total: {len(self._clients)})")

    async def unregister_client(self, websocket) -> None:
        """Remove a disconnected WebSocket client."""
        self._clients.discard(websocket)
        logger.info(f"Video client disconnected (total: {len(self._clients)})")

    async def stream_loop(self) -> None:
        """Main streaming loop — captures and broadcasts frames."""
        self._running = True
        logger.info(
            f"Video server started (target: {self._target_fps} FPS, "
            f"quality: {self._jpeg_quality})"
        )

        while self._running:
            if not self._clients:
                await asyncio.sleep(0.1)
                continue

            start = time.time()

            # Capture frame
            frame = self._camera.get_frame()
            if frame is None:
                await asyncio.sleep(self._frame_interval)
                continue

            # Draw overlays
            frame = self._overlay.draw(frame, self._current_tracks)
            frame = self._overlay.draw_status(
                frame,
                self._mission_state,
                self._battery_pct,
                self._altitude_m,
                self._fps_counter.fps,
            )

            # Encode as JPEG
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
            _, jpeg_bytes = cv2.imencode(".jpg", frame, encode_params)
            data = jpeg_bytes.tobytes()

            # Broadcast to all clients
            disconnected = set()
            for ws in self._clients.copy():
                try:
                    await ws.send_bytes(data)
                except Exception:
                    disconnected.add(ws)

            for ws in disconnected:
                await self.unregister_client(ws)

            self._fps_counter.tick()

            # Rate limiting
            elapsed = time.time() - start
            sleep_time = max(0, self._frame_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    def stop(self) -> None:
        """Stop the streaming loop."""
        self._running = False
        logger.info("Video server stopped")

    def get_snapshot(self) -> Optional[bytes]:
        """Get a single JPEG snapshot (for HTTP endpoint)."""
        frame = self._camera.get_frame()
        if frame is None:
            return None

        frame = self._overlay.draw(frame, self._current_tracks)
        _, jpeg = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        )
        return jpeg.tobytes()


class _FPSCounter:
    """Simple FPS counter."""

    def __init__(self, window: int = 30):
        self._times: list[float] = []
        self._window = window

    def tick(self):
        self._times.append(time.time())
        if len(self._times) > self._window:
            self._times.pop(0)

    @property
    def fps(self) -> float:
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        if elapsed <= 0:
            return 0.0
        return (len(self._times) - 1) / elapsed
