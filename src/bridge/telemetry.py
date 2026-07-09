"""
Telemetry — Dedicated telemetry data collector and publisher.

Provides an async queue-based interface for other modules
(dashboard, safety monitor) to consume telemetry data.
"""

import asyncio
import logging
from typing import Optional

from src.bridge.mavlink_bridge import MAVLinkBridge, TelemetryFrame

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """Collects telemetry from MAVLink bridge and distributes to subscribers.

    Provides an async queue for each subscriber, ensuring no data is lost
    and each consumer gets every update.
    """

    def __init__(self, bridge: MAVLinkBridge, max_queue_size: int = 100):
        self._bridge = bridge
        self._subscribers: list[asyncio.Queue[TelemetryFrame]] = []
        self._max_queue_size = max_queue_size
        self._running = False

    def subscribe(self) -> asyncio.Queue[TelemetryFrame]:
        """Create a new subscriber queue.

        Returns:
            An asyncio.Queue that will receive TelemetryFrame updates.
        """
        queue: asyncio.Queue[TelemetryFrame] = asyncio.Queue(
            maxsize=self._max_queue_size
        )
        self._subscribers.append(queue)
        logger.debug(f"New telemetry subscriber (total: {len(self._subscribers)})")
        return queue

    def unsubscribe(self, queue: asyncio.Queue[TelemetryFrame]) -> None:
        """Remove a subscriber queue."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)
            logger.debug(
                f"Telemetry subscriber removed (total: {len(self._subscribers)})"
            )

    async def _on_telemetry(self, frame: TelemetryFrame) -> None:
        """Callback from MAVLink bridge — distributes to all subscribers."""
        for queue in self._subscribers:
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                # Drop oldest if full (non-blocking)
                try:
                    queue.get_nowait()
                    queue.put_nowait(frame)
                except asyncio.QueueEmpty:
                    pass

    async def start(self, rate_hz: float = 10.0) -> None:
        """Start collecting telemetry from the bridge."""
        self._running = True
        await self._bridge.start_telemetry_stream(
            rate_hz=rate_hz, callback=self._on_telemetry
        )
        logger.info(f"Telemetry collector started at {rate_hz} Hz")

    async def stop(self) -> None:
        """Stop telemetry collection."""
        self._running = False
        await self._bridge.stop_telemetry_stream()
        logger.info("Telemetry collector stopped")

    @property
    def latest(self) -> Optional[TelemetryFrame]:
        """Get the latest telemetry frame (non-blocking)."""
        return self._bridge.latest_telemetry
