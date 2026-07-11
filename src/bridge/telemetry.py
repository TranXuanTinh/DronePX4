"""
Telemetry Collector — distributes telemetry via EventBus.

Uses the Observer pattern (EventBus) instead of manual queue-based
subscriber management. Also retains the legacy queue-based API for
backward compatibility with WebSocket endpoints.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from src.core.interfaces import DroneConnector
from src.core.types import TelemetryFrame, TelemetryEvent
from src.core.events import EventBus

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """Collects telemetry from a DroneConnector and distributes it.

    Two distribution mechanisms (both active simultaneously):
    1. EventBus (Observer pattern) — preferred for new consumers.
    2. Queue-based subscription — retained for WebSocket streaming.
    """

    def __init__(
        self,
        connector: DroneConnector,
        event_bus: Optional[EventBus] = None,
        max_queue_size: int = 100,
    ) -> None:
        self._connector = connector
        self._event_bus = event_bus
        self._subscribers: list[asyncio.Queue[TelemetryFrame]] = []
        self._max_queue_size = max_queue_size
        self._running = False

    # ── Queue-based API (WebSocket compat) ───────────────────

    def subscribe(self) -> asyncio.Queue[TelemetryFrame]:
        """Create a new subscriber queue.

        Returns:
            An asyncio.Queue that will receive TelemetryFrame updates.
        """
        queue: asyncio.Queue[TelemetryFrame] = asyncio.Queue(
            maxsize=self._max_queue_size,
        )
        self._subscribers.append(queue)
        logger.debug(
            f"New telemetry subscriber (total: {len(self._subscribers)})"
        )
        return queue

    def unsubscribe(self, queue: asyncio.Queue[TelemetryFrame]) -> None:
        """Remove a subscriber queue."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)
            logger.debug(
                f"Telemetry subscriber removed "
                f"(total: {len(self._subscribers)})"
            )

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self, rate_hz: float = 10.0) -> None:
        """Start collecting telemetry from the connector."""
        self._running = True
        await self._connector.start_telemetry_stream(
            rate_hz=rate_hz, callback=self._on_telemetry,
        )
        logger.info(f"Telemetry collector started at {rate_hz} Hz")

    async def stop(self) -> None:
        """Stop telemetry collection."""
        self._running = False
        await self._connector.stop_telemetry_stream()
        logger.info("Telemetry collector stopped")

    @property
    def latest(self) -> Optional[TelemetryFrame]:
        """Get the latest telemetry frame (non-blocking)."""
        return self._connector.latest_telemetry

    # ── Private ──────────────────────────────────────────────

    async def _on_telemetry(self, frame: TelemetryFrame) -> None:
        """Callback from DroneConnector — distributes to all consumers."""
        # Publish via EventBus (Observer pattern)
        if self._event_bus:
            await self._event_bus.publish(TelemetryEvent(frame=frame))

        # Publish via queues (WebSocket compat)
        for queue in self._subscribers:
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(frame)
                except asyncio.QueueEmpty:
                    pass
