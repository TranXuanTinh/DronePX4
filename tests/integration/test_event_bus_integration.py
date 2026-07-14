"""
Integration tests: EventBus cross-subsystem communication.

Validates that events published by one subsystem are correctly
received by subscribers in other subsystems.

DO-178C Traceability: REQ-EVENT-INT-001 through REQ-EVENT-INT-004
"""
import asyncio
import pytest

from src.core.events import EventBus
from src.core.types import (
    TelemetryEvent, StateChangeEvent, DetectionFoundEvent,
    TelemetryFrame, GeotaggedDetection,
)
import numpy as np


@pytest.mark.integration
class TestEventBusCrossSubsystem:
    """Test EventBus message delivery between subsystems."""

    @pytest.mark.asyncio
    async def test_telemetry_event_reaches_subscribers(
        self, integration_event_bus, make_telemetry
    ):
        """REQ-EVENT-INT-001: TelemetryEvent reaches safety subscriber."""
        received = []
        integration_event_bus.subscribe(
            TelemetryEvent, lambda e: received.append(e)
        )

        telem = make_telemetry()
        await integration_event_bus.publish(TelemetryEvent(frame=telem))

        assert len(received) == 1
        assert received[0].frame.battery_percent == 80.0

    @pytest.mark.asyncio
    async def test_state_change_event_delivery(self, integration_event_bus):
        """REQ-EVENT-INT-002: StateChangeEvent reaches dashboard subscriber."""
        received = []
        integration_event_bus.subscribe(
            StateChangeEvent, lambda e: received.append(e)
        )

        event = StateChangeEvent(old_state="IDLE", new_state="PREFLIGHT")
        await integration_event_bus.publish(event)

        assert len(received) == 1
        assert received[0].new_state == "PREFLIGHT"

    @pytest.mark.asyncio
    async def test_detection_event_delivery(self, integration_event_bus):
        """REQ-EVENT-INT-003: DetectionFoundEvent reaches log subscriber."""
        received = []
        integration_event_bus.subscribe(
            DetectionFoundEvent, lambda e: received.append(e)
        )

        detection = GeotaggedDetection(
            track_id=1, class_name="person", confidence=0.9,
            bbox=np.array([10, 20, 30, 40]),
            pixel_center=(20, 30),
            latitude_deg=47.3977, longitude_deg=8.5456,
            drone_altitude_m=20.0, timestamp=100.0,
        )
        await integration_event_bus.publish(DetectionFoundEvent(detection=detection))

        assert len(received) == 1
        assert received[0].detection.class_name == "person"

    @pytest.mark.asyncio
    async def test_error_in_subscriber_does_not_block_others(
        self, integration_event_bus
    ):
        """REQ-EVENT-INT-004: Faulty subscriber doesn't break others."""
        good_received = []

        def bad_handler(e):
            raise RuntimeError("subscriber crash")

        def good_handler(e):
            good_received.append(e)

        integration_event_bus.subscribe(StateChangeEvent, bad_handler)
        integration_event_bus.subscribe(StateChangeEvent, good_handler)

        event = StateChangeEvent(old_state="A", new_state="B")
        await integration_event_bus.publish(event)

        assert len(good_received) == 1

    @pytest.mark.asyncio
    async def test_different_event_types_are_isolated(
        self, integration_event_bus, make_telemetry
    ):
        """REQ-EVENT-INT-004: Events of different types don't cross."""
        telem_count = [0]
        state_count = [0]

        integration_event_bus.subscribe(
            TelemetryEvent, lambda e: telem_count.__setitem__(0, telem_count[0] + 1)
        )
        integration_event_bus.subscribe(
            StateChangeEvent, lambda e: state_count.__setitem__(0, state_count[0] + 1)
        )

        await integration_event_bus.publish(
            StateChangeEvent(old_state="A", new_state="B")
        )

        assert state_count[0] == 1
        assert telem_count[0] == 0
