"""
Shared data types (DTOs) — single source of truth for the entire project.

All value objects and data transfer objects live here. Modules import
types from this file instead of defining their own, eliminating
duplication and ensuring consistency.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum, Enum
from typing import Tuple

import numpy as np


# ──────────────────────────────────────────────────────────────
# GPS / Telemetry
# ──────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Position:
    """Immutable GPS position."""
    latitude_deg: float
    longitude_deg: float
    absolute_altitude_m: float
    relative_altitude_m: float


@dataclass(frozen=True, slots=True)
class Attitude:
    """Immutable vehicle attitude (Euler angles)."""
    roll_deg: float
    pitch_deg: float
    yaw_deg: float


@dataclass(slots=True)
class TelemetryFrame:
    """Aggregated telemetry snapshot.

    Mutable because the bridge updates individual fields
    from separate MAVSDK streams.
    """
    timestamp: float = 0.0
    position: Position = field(default_factory=lambda: Position(0, 0, 0, 0))
    attitude: Attitude = field(default_factory=lambda: Attitude(0, 0, 0))
    heading_deg: float = 0.0
    groundspeed_ms: float = 0.0
    battery_percent: float = 100.0
    battery_voltage: float = 0.0
    flight_mode: str = "UNKNOWN"
    armed: bool = False
    is_connected: bool = False
    gps_num_satellites: int = 0
    gps_fix_type: int = 0


# ──────────────────────────────────────────────────────────────
# Mission
# ──────────────────────────────────────────────────────────────

class MissionState(str, Enum):
    """Canonical mission states — used by state machine AND API schemas."""
    IDLE = "IDLE"
    PREFLIGHT = "PREFLIGHT"
    TAKEOFF = "TAKEOFF"
    SEARCH = "SEARCH"
    DETECT = "DETECT"
    INSPECT = "INSPECT"
    LOG = "LOG"
    RTL = "RTL"
    LANDED = "LANDED"
    ABORT = "ABORT"


@dataclass(slots=True)
class Waypoint:
    """A single mission waypoint."""
    latitude: float    # degrees
    longitude: float   # degrees
    altitude: float    # meters (AMSL or relative, depending on use)
    index: int = 0     # Waypoint number in sequence

    def __repr__(self) -> str:
        return (
            f"WP{self.index}({self.latitude:.6f}, {self.longitude:.6f}, "
            f"alt={self.altitude:.1f}m)"
        )


# ──────────────────────────────────────────────────────────────
# Safety
# ──────────────────────────────────────────────────────────────

class SafetyAction(IntEnum):
    """Safety actions ordered by priority (higher = more urgent)."""
    NONE = 0
    WARN = 1
    RTL_NOW = 2
    EMERGENCY_LAND = 3


# ──────────────────────────────────────────────────────────────
# Perception
# ──────────────────────────────────────────────────────────────

@dataclass(slots=True)
class Detection:
    """Single object detection result from a detector."""
    bbox: np.ndarray         # [x1, y1, x2, y2] in pixels
    class_id: int
    class_name: str
    confidence: float

    @property
    def center(self) -> Tuple[int, int]:
        """Bounding box center (x, y)."""
        return (
            int((self.bbox[0] + self.bbox[2]) / 2),
            int((self.bbox[1] + self.bbox[3]) / 2),
        )

    @property
    def area(self) -> float:
        """Bounding box area in pixels."""
        return float(
            (self.bbox[2] - self.bbox[0]) * (self.bbox[3] - self.bbox[1])
        )


@dataclass(slots=True)
class Track:
    """A tracked object with persistent ID across frames."""
    track_id: int
    bbox: np.ndarray         # [x1, y1, x2, y2]
    class_id: int
    class_name: str
    confidence: float
    age: int                 # Number of frames this track has existed
    is_confirmed: bool       # Whether track has enough history

    @property
    def center(self) -> Tuple[int, int]:
        return (
            int((self.bbox[0] + self.bbox[2]) / 2),
            int((self.bbox[1] + self.bbox[3]) / 2),
        )


@dataclass(slots=True)
class GeotaggedDetection:
    """A tracked detection with estimated GPS coordinates."""
    track_id: int
    class_name: str
    confidence: float
    bbox: np.ndarray          # [x1, y1, x2, y2] in pixels
    pixel_center: Tuple[int, int]
    latitude_deg: float       # Estimated ground GPS
    longitude_deg: float
    drone_altitude_m: float
    timestamp: float


# ──────────────────────────────────────────────────────────────
# Events (for EventBus)
# ──────────────────────────────────────────────────────────────

@dataclass(slots=True)
class TelemetryEvent:
    """Published by the telemetry collector at a fixed rate."""
    frame: TelemetryFrame


@dataclass(slots=True)
class DetectionFoundEvent:
    """Published when the perception pipeline confirms a new detection."""
    detection: GeotaggedDetection


@dataclass(slots=True)
class StateChangeEvent:
    """Published when the mission state machine changes state."""
    old_state: str
    new_state: str
    timestamp: float = field(default_factory=time.time)
