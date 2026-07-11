"""
Event Bus — lightweight Observer pattern implementation.

Decouples publishers from subscribers. Replaces manual callback wiring
and polling loops with a typed, async-aware publish/subscribe system.

Usage:
    bus = EventBus()
    bus.subscribe(TelemetryEvent, my_handler)
    await bus.publish(TelemetryEvent(frame=telem))
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Type

logger = logging.getLogger(__name__)


class EventBus:
    """In-process async event bus (Observer pattern).

    Supports both sync and async handlers. Thread-safe enough for
    single-process asyncio usage.

    Can be swapped for ROS 2 topics or Redis pub/sub in production
    by implementing the same interface.
    """

    def __init__(self) -> None:
        self._handlers: Dict[Type, List[Callable]] = defaultdict(list)

    def subscribe(self, event_type: Type, handler: Callable) -> None:
        """Register a handler for an event type.

        Args:
            event_type: The event class to listen for.
            handler: Callable (sync or async) that takes one argument — the event.
        """
        self._handlers[event_type].append(handler)
        logger.debug(
            f"Subscribed {handler.__qualname__} to {event_type.__name__}"
        )

    def unsubscribe(self, event_type: Type, handler: Callable) -> None:
        """Remove a handler for an event type."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Any) -> None:
        """Publish an event to all subscribers.

        Async handlers are awaited; sync handlers are called directly.
        Errors in individual handlers are logged but do not prevent
        other handlers from being called.

        Args:
            event: Event instance to publish.
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                logger.exception(
                    f"Error in handler {handler.__qualname__} "
                    f"for {event_type.__name__}"
                )

    def clear(self) -> None:
        """Remove all subscriptions."""
        self._handlers.clear()

    @property
    def subscriber_count(self) -> int:
        """Total number of subscriptions across all event types."""
        return sum(len(h) for h in self._handlers.values())
