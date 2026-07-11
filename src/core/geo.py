"""
GPS math utilities — single source of truth.

Consolidates haversine distance and GPS offset calculations that were
previously duplicated across safety.py, state_machine.py,
waypoint_planner.py, and geotagging.py.
"""
from __future__ import annotations

import math
from typing import Tuple

# WGS84 mean Earth radius in meters
EARTH_RADIUS_M: float = 6_371_000.0


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float,
) -> float:
    """Calculate great-circle distance between two GPS points.

    Args:
        lat1, lon1: First point (degrees).
        lat2, lon2: Second point (degrees).

    Returns:
        Distance in meters.
    """
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def offset_gps(
    lat: float, lon: float, north_m: float, east_m: float,
) -> Tuple[float, float]:
    """Offset a GPS coordinate by meters North and East.

    Uses a simple flat-Earth approximation (accurate within ~10 km).

    Args:
        lat: Starting latitude (degrees).
        lon: Starting longitude (degrees).
        north_m: Northward offset in meters.
        east_m: Eastward offset in meters.

    Returns:
        Tuple of (new_lat, new_lon) in degrees.
    """
    lat_offset = north_m / EARTH_RADIUS_M * (180.0 / math.pi)
    lon_offset = east_m / (
        EARTH_RADIUS_M * math.cos(math.radians(lat))
    ) * (180.0 / math.pi)
    return lat + lat_offset, lon + lon_offset
