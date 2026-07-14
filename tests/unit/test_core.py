"""
Unit tests for EventBus — Observer pattern.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.events import EventBus
from src.core.types import TelemetryEvent, StateChangeEvent, TelemetryFrame
import pytest

@pytest.mark.unit
class TestEventBus:
    """Test the Observer pattern event bus."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(StateChangeEvent, handler)
        event = StateChangeEvent(old_state="IDLE", new_state="PREFLIGHT")
        await bus.publish(event)
        assert len(received) == 1
        assert received[0].new_state == "PREFLIGHT"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        bus = EventBus()
        count = [0, 0]

        def handler1(e): count[0] += 1
        def handler2(e): count[1] += 1

        bus.subscribe(StateChangeEvent, handler1)
        bus.subscribe(StateChangeEvent, handler2)
        event = StateChangeEvent(old_state="A", new_state="B")
        await bus.publish(event)
        assert count == [1, 1]

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        bus = EventBus()
        received = []

        def handler(e): received.append(e)

        bus.subscribe(StateChangeEvent, handler)
        bus.unsubscribe(StateChangeEvent, handler)
        event = StateChangeEvent(old_state="A", new_state="B")
        await bus.publish(event)
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_different_event_types_isolated(self):
        bus = EventBus()
        state_count = [0]
        telem_count = [0]

        def state_handler(e): state_count[0] += 1
        def telem_handler(e): telem_count[0] += 1

        bus.subscribe(StateChangeEvent, state_handler)
        bus.subscribe(TelemetryEvent, telem_handler)

        await bus.publish(StateChangeEvent("A", "B"))
        assert state_count[0] == 1
        assert telem_count[0] == 0

    @pytest.mark.asyncio
    async def test_handler_error_isolated(self):
        bus = EventBus()
        received = []

        def bad_handler(e): raise ValueError("boom")
        def good_handler(e): received.append(e)

        bus.subscribe(StateChangeEvent, bad_handler)
        bus.subscribe(StateChangeEvent, good_handler)

        event = StateChangeEvent("A", "B")
        await bus.publish(event)
        # good_handler should still be called despite bad_handler error
        assert len(received) == 1

    def test_clear(self):
        bus = EventBus()
        bus.subscribe(StateChangeEvent, lambda e: None)
        bus.subscribe(TelemetryEvent, lambda e: None)
        assert bus.subscriber_count == 2
        bus.clear()
        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_async_handler(self):
        bus = EventBus()
        received = []

        async def async_handler(e):
            received.append(e)

        bus.subscribe(StateChangeEvent, async_handler)
        event = StateChangeEvent("A", "B")
        await bus.publish(event)
        assert len(received) == 1


class TestCoreGeo:
    """Test core.geo utilities."""

    def test_haversine_same_point(self):
        from src.core.geo import haversine_distance
        d = haversine_distance(47.3977, 8.5456, 47.3977, 8.5456)
        assert d < 0.01

    def test_offset_roundtrip(self):
        from src.core.geo import offset_gps, haversine_distance
        lat2, lon2 = offset_gps(47.3977, 8.5456, 100, 0)
        d = haversine_distance(47.3977, 8.5456, lat2, lon2)
        assert abs(d - 100) < 1.0
