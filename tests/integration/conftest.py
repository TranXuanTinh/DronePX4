"""
Integration test fixtures — cross-subsystem wiring tests.
"""
import pytest
from src.core.events import EventBus


@pytest.fixture
def integration_event_bus():
    """Fresh EventBus for integration tests."""
    bus = EventBus()
    yield bus
    bus.clear()
