"""
Dependencies — typed DI container for the dashboard backend.

Replaces the untyped `app_state = {}` global dict with a proper
dataclass container. Provides type safety and IDE autocompletion.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

import asyncio

from src.core.interfaces import (
    DroneConnector, FlightController, ObjectDetector,
    ObjectTracker, Geotagger, CameraSource, SafetyChecker,
)
from src.core.types import GeotaggedDetection
from src.core.events import EventBus
from src.bridge.telemetry import TelemetryCollector
from src.streaming.video_server import VideoServer
from src.mission.state_machine import MissionStateMachine


@dataclass
class AppContainer:
    """Typed dependency injection container.

    All subsystem instances in one place, with proper types.
    Initialized during FastAPI lifespan startup.
    """
    connector: Optional[DroneConnector] = None
    flight: Optional[FlightController] = None
    telemetry_collector: Optional[TelemetryCollector] = None
    camera: Optional[CameraSource] = None
    detector: Optional[ObjectDetector] = None
    tracker: Optional[ObjectTracker] = None
    geotagger: Optional[Geotagger] = None
    video_server: Optional[VideoServer] = None
    state_machine: Optional[MissionStateMachine] = None
    safety: Optional[SafetyChecker] = None
    event_bus: EventBus = field(default_factory=EventBus)
    config: dict = field(default_factory=dict)
    detections: List[GeotaggedDetection] = field(default_factory=list)
    mission_task: Optional[asyncio.Task] = None
    start_time: float = field(default_factory=time.time)


# Singleton container — populated during lifespan
container = AppContainer()
