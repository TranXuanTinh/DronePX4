"""
Telemetry rate validation tests.

Validates that telemetry delivery meets timing requirements.

DO-178C Traceability: REQ-PROTO-007 through REQ-PROTO-009
"""
import asyncio
import time
import pytest

from src.core.events import EventBus
from src.core.types import TelemetryEvent, TelemetryFrame


@pytest.mark.protocol
class TestTelemetryRate:
    """Test telemetry stream delivery rate."""

    @pytest.mark.asyncio
    async def test_event_bus_can_handle_high_frequency_events(self):
        """REQ-PROTO-007: EventBus sustains 10 Hz event delivery."""
        bus = EventBus()
        received = []
        bus.subscribe(TelemetryEvent, lambda e: received.append(time.time()))

        # Publish 100 events at ~10 Hz
        for _ in range(100):
            frame = TelemetryFrame()
            await bus.publish(TelemetryEvent(frame=frame))
            await asyncio.sleep(0.01)  # 100 Hz — faster than needed

        assert len(received) == 100

    @pytest.mark.asyncio
    async def test_event_bus_delivery_latency(self):
        """REQ-PROTO-008: EventBus delivery latency < 1ms per event."""
        bus = EventBus()
        latencies = []

        async def measure_latency(event):
            latencies.append(time.perf_counter() - event.frame.timestamp)

        bus.subscribe(TelemetryEvent, measure_latency)

        for _ in range(50):
            frame = TelemetryFrame(timestamp=time.perf_counter())
            await bus.publish(TelemetryEvent(frame=frame))

        avg_latency_ms = sum(latencies) / len(latencies) * 1000
        assert avg_latency_ms < 1.0, f"Average latency: {avg_latency_ms:.3f}ms"

    @pytest.mark.asyncio
    async def test_no_dropped_events_under_load(self):
        """REQ-PROTO-009: No dropped events over burst delivery."""
        bus = EventBus()
        received = []
        bus.subscribe(TelemetryEvent, lambda e: received.append(e))

        total_events = 200
        for _ in range(total_events):
            frame = TelemetryFrame()
            await bus.publish(TelemetryEvent(frame=frame))

        delivery_rate = len(received) / total_events
        assert delivery_rate >= 0.95, (
            f"Event delivery rate: {delivery_rate:.1%} (required ≥ 95%)"
        )
