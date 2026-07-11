"""
Waypoint Planner — Strategy pattern for search patterns.

Each pattern is a separate class implementing SearchPatternStrategy.
The PatternRegistry auto-discovers patterns — adding a new pattern
requires only creating a new class and registering it (OCP).
"""
from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Type

from src.core.interfaces import SearchPatternStrategy
from src.core.types import Waypoint
from src.core.geo import offset_gps

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Pattern Registry (auto-discovery)
# ──────────────────────────────────────────────────────────────

class PatternRegistry:
    """Registry of available search patterns.

    To add a new pattern:
    1. Create a class implementing SearchPatternStrategy.
    2. Call PatternRegistry.register(MyPattern).
    """

    _patterns: Dict[str, SearchPatternStrategy] = {}

    @classmethod
    def register(cls, pattern: SearchPatternStrategy) -> None:
        cls._patterns[pattern.name] = pattern
        logger.debug(f"Registered search pattern: {pattern.name}")

    @classmethod
    def get(cls, name: str) -> Optional[SearchPatternStrategy]:
        return cls._patterns.get(name)

    @classmethod
    def available(cls) -> List[str]:
        return list(cls._patterns.keys())

    @classmethod
    def generate(cls, name: str, config: dict) -> List[Waypoint]:
        """Generate waypoints using a named pattern.

        Args:
            name: Pattern name (e.g., "lawnmower").
            config: Pattern-specific configuration dict.

        Returns:
            List of Waypoint objects.

        Raises:
            ValueError: If pattern name is not registered.
        """
        pattern = cls.get(name)
        if pattern is None:
            raise ValueError(
                f"Unknown pattern '{name}'. "
                f"Available: {cls.available()}"
            )
        return pattern.generate(config)


# ──────────────────────────────────────────────────────────────
# Concrete Strategy Implementations
# ──────────────────────────────────────────────────────────────

class LawnmowerPattern(SearchPatternStrategy):
    """Lawnmower (boustrophedon) search pattern.

    Creates parallel passes across a rectangular area,
    alternating direction on each pass.
    """

    @property
    def name(self) -> str:
        return "lawnmower"

    def generate(self, config: dict) -> List[Waypoint]:
        center_lat = config.get("center_lat", 47.397742)
        center_lon = config.get("center_lon", 8.545594)
        width_m = config.get("width_m", 200.0)
        height_m = config.get("height_m", 150.0)
        spacing_m = config.get("spacing_m", 30.0)
        altitude_m = config.get("altitude_m", 20.0)

        waypoints: List[Waypoint] = []
        idx = 0

        num_passes = max(1, int(width_m / spacing_m) + 1)
        half_h = height_m / 2
        half_w = width_m / 2

        for i in range(num_passes):
            east_offset = min(-half_w + i * spacing_m, half_w)

            if i % 2 == 0:
                north_offsets = [-half_h, half_h]
            else:
                north_offsets = [half_h, -half_h]

            for north_offset in north_offsets:
                lat, lon = offset_gps(
                    center_lat, center_lon, north_offset, east_offset,
                )
                waypoints.append(Waypoint(
                    latitude=lat, longitude=lon,
                    altitude=altitude_m, index=idx,
                ))
                idx += 1

        logger.info(
            f"Generated lawnmower pattern: {len(waypoints)} waypoints "
            f"over {width_m}×{height_m}m area with {spacing_m}m spacing"
        )
        return waypoints


class ExpandingSquarePattern(SearchPatternStrategy):
    """Expanding square search pattern.

    Spirals outward from center in a square pattern.
    """

    @property
    def name(self) -> str:
        return "expanding_square"

    def generate(self, config: dict) -> List[Waypoint]:
        center_lat = config.get("center_lat", 47.397742)
        center_lon = config.get("center_lon", 8.545594)
        initial_radius_m = config.get("initial_radius_m", 20.0)
        expansion_m = config.get("expansion_m", 15.0)
        max_radius_m = config.get("max_radius_m", 100.0)
        altitude_m = config.get("altitude_m", 20.0)

        waypoints: List[Waypoint] = []
        idx = 0

        # Start at center
        waypoints.append(Waypoint(center_lat, center_lon, altitude_m, idx))
        idx += 1

        leg = initial_radius_m
        direction = 0  # 0=N, 1=E, 2=S, 3=W

        while leg <= max_radius_m:
            for _ in range(2):
                if direction == 0:
                    n_off, e_off = leg, 0
                elif direction == 1:
                    n_off, e_off = 0, leg
                elif direction == 2:
                    n_off, e_off = -leg, 0
                else:
                    n_off, e_off = 0, -leg

                prev = waypoints[-1]
                lat, lon = offset_gps(
                    prev.latitude, prev.longitude, n_off, e_off,
                )
                waypoints.append(Waypoint(lat, lon, altitude_m, idx))
                idx += 1
                direction = (direction + 1) % 4

            leg += expansion_m

        logger.info(
            f"Generated expanding square: {len(waypoints)} waypoints, "
            f"max radius {max_radius_m}m"
        )
        return waypoints


class CustomWaypointsPattern(SearchPatternStrategy):
    """Custom waypoints from a list of coordinate dicts."""

    @property
    def name(self) -> str:
        return "custom"

    def generate(self, config: dict) -> List[Waypoint]:
        waypoint_dicts = config.get("waypoints", [])
        altitude_m = config.get("altitude_m", 20.0)

        waypoints = []
        for i, wp in enumerate(waypoint_dicts):
            waypoints.append(Waypoint(
                latitude=wp["lat"],
                longitude=wp["lon"],
                altitude=wp.get("alt", altitude_m),
                index=i,
            ))

        logger.info(f"Loaded {len(waypoints)} custom waypoints")
        return waypoints


# ──────────────────────────────────────────────────────────────
# Auto-register built-in patterns
# ──────────────────────────────────────────────────────────────

PatternRegistry.register(LawnmowerPattern())
PatternRegistry.register(ExpandingSquarePattern())
PatternRegistry.register(CustomWaypointsPattern())


# ──────────────────────────────────────────────────────────────
# Backward Compatibility
# ──────────────────────────────────────────────────────────────

class WaypointPlanner:
    """Legacy API — delegates to PatternRegistry.

    Kept for backward compatibility with existing code that calls
    WaypointPlanner.lawnmower(...) directly.
    """

    @staticmethod
    def lawnmower(
        center_lat: float, center_lon: float,
        width_m: float, height_m: float,
        spacing_m: float, altitude_m: float,
    ) -> List[Waypoint]:
        return PatternRegistry.generate("lawnmower", {
            "center_lat": center_lat, "center_lon": center_lon,
            "width_m": width_m, "height_m": height_m,
            "spacing_m": spacing_m, "altitude_m": altitude_m,
        })

    @staticmethod
    def expanding_square(
        center_lat: float, center_lon: float,
        initial_radius_m: float, expansion_m: float,
        max_radius_m: float, altitude_m: float,
    ) -> List[Waypoint]:
        return PatternRegistry.generate("expanding_square", {
            "center_lat": center_lat, "center_lon": center_lon,
            "initial_radius_m": initial_radius_m,
            "expansion_m": expansion_m,
            "max_radius_m": max_radius_m,
            "altitude_m": altitude_m,
        })

    @staticmethod
    def custom_waypoints(
        waypoint_dicts: List[dict], altitude_m: float,
    ) -> List[Waypoint]:
        return PatternRegistry.generate("custom", {
            "waypoints": waypoint_dicts,
            "altitude_m": altitude_m,
        })
