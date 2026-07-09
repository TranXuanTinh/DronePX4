"""
Pydantic schemas for the dashboard API.

Defines data models for telemetry, detections, mission status,
and report generation — shared between backend and WebSocket endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# === Telemetry ===

class TelemetryData(BaseModel):
    """Real-time telemetry snapshot sent via WebSocket."""
    timestamp: float
    latitude: float
    longitude: float
    altitude_m: float
    heading_deg: float
    groundspeed_ms: float
    battery_percent: float
    battery_voltage: float
    flight_mode: str
    armed: bool
    gps_satellites: int
    gps_fix_type: int
    mission_state: str = "IDLE"
    is_connected: bool = True


# === Detections ===

class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class DetectionEvent(BaseModel):
    """A single geotagged detection event."""
    id: str
    timestamp: float
    track_id: int
    class_name: str
    confidence: float
    latitude: float
    longitude: float
    altitude_m: float
    bbox: BoundingBox
    image_path: Optional[str] = None


class DetectionListResponse(BaseModel):
    """Response for GET /api/detections."""
    total: int
    detections: List[DetectionEvent]


# === Mission ===

class MissionStateEnum(str, Enum):
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


class MissionStatus(BaseModel):
    """Current mission status."""
    state: str
    elapsed_seconds: float = 0.0
    waypoints_total: int = 0
    waypoints_completed: int = 0
    detections_count: int = 0
    battery_percent: float = 100.0
    is_connected: bool = True


class MissionStartRequest(BaseModel):
    """Request body for starting a mission."""
    pattern: str = "lawnmower"
    center_lat: Optional[float] = None
    center_lon: Optional[float] = None
    width_m: float = 200.0
    height_m: float = 150.0
    spacing_m: float = 30.0
    altitude_m: float = 20.0


class MissionCommandResponse(BaseModel):
    """Response for mission control commands."""
    success: bool
    message: str
    state: str


# === System Status ===

class SystemStatus(BaseModel):
    """Overall system health."""
    sitl_connected: bool
    flight_mode: str
    armed: bool
    gps_fix: bool
    battery_percent: float
    mission_state: str
    uptime_seconds: float
    detection_count: int
    avg_inference_ms: float


# === Reports ===

class ReportRequest(BaseModel):
    """Request parameters for report generation."""
    format: str = "pdf"  # pdf | csv
    include_images: bool = True


class ReportResponse(BaseModel):
    """Response after report generation."""
    success: bool
    file_path: str
    file_size_bytes: int
    detection_count: int
