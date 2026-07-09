"""
Waypoint Planner — Generate search patterns for inspection missions.

Supports lawnmower (boustrophedon), expanding square, and custom patterns.
All coordinates are in WGS84 (latitude/longitude degrees).
"""

import logging
import math
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

EARTH_RADIUS_M = 6_371_000.0


@dataclass
class Waypoint:
    """A single mission waypoint."""
    latitude: float    # degrees
    longitude: float   # degrees
    altitude: float    # meters (AMSL or relative, depending on use)
    index: int = 0     # Waypoint number in sequence

    def __repr__(self):
        return (
            f"WP{self.index}({self.latitude:.6f}, {self.longitude:.6f}, "
            f"alt={self.altitude:.1f}m)"
        )


class WaypointPlanner:
    """Generate search patterns for inspection missions."""

    @staticmethod
    def lawnmower(
        center_lat: float,
        center_lon: float,
        width_m: float,
        height_m: float,
        spacing_m: float,
        altitude_m: float,
    ) -> List[Waypoint]:
        """Generate lawnmower (boustrophedon) search pattern.

        Creates parallel passes across a rectangular area,
        alternating direction on each pass.

        Args:
            center_lat: Center latitude of search area
            center_lon: Center longitude of search area
            width_m: East-West extent in meters
            height_m: North-South extent in meters
            spacing_m: Distance between passes in meters
            altitude_m: Flight altitude in meters

        Returns:
            List of Waypoint objects defining the pattern.
        """
        waypoints = []
        idx = 0

        # Calculate number of passes
        num_passes = max(1, int(width_m / spacing_m) + 1)

        # Half extents
        half_h = height_m / 2
        half_w = width_m / 2

        for i in range(num_passes):
            # East offset for this pass
            east_offset = -half_w + i * spacing_m
            east_offset = min(east_offset, half_w)

            if i % 2 == 0:
                # South to North
                north_offsets = [-half_h, half_h]
            else:
                # North to South
                north_offsets = [half_h, -half_h]

            for north_offset in north_offsets:
                lat, lon = WaypointPlanner._offset_gps(
                    center_lat, center_lon, north_offset, east_offset
                )
                waypoints.append(
                    Waypoint(
                        latitude=lat,
                        longitude=lon,
                        altitude=altitude_m,
                        index=idx,
                    )
                )
                idx += 1

        logger.info(
            f"Generated lawnmower pattern: {len(waypoints)} waypoints "
            f"over {width_m}×{height_m}m area with {spacing_m}m spacing"
        )
        return waypoints

    @staticmethod
    def expanding_square(
        center_lat: float,
        center_lon: float,
        initial_radius_m: float,
        expansion_m: float,
        max_radius_m: float,
        altitude_m: float,
    ) -> List[Waypoint]:
        """Generate expanding square search pattern.

        Spirals outward from center in a square pattern.

        Args:
            center_lat: Center latitude
            center_lon: Center longitude
            initial_radius_m: Starting distance from center
            expansion_m: Distance added per spiral leg
            max_radius_m: Maximum distance from center
            altitude_m: Flight altitude

        Returns:
            List of Waypoint objects.
        """
        waypoints = []
        idx = 0

        # Start at center
        waypoints.append(
            Waypoint(center_lat, center_lon, altitude_m, idx)
        )
        idx += 1

        leg = initial_radius_m
        direction = 0  # 0=N, 1=E, 2=S, 3=W

        while leg <= max_radius_m:
            # Two legs of the same length per direction pair
            for _ in range(2):
                if direction == 0:  # North
                    n_off, e_off = leg, 0
                elif direction == 1:  # East
                    n_off, e_off = 0, leg
                elif direction == 2:  # South
                    n_off, e_off = -leg, 0
                else:  # West
                    n_off, e_off = 0, -leg

                # Calculate cumulative offset from center
                prev = waypoints[-1]
                lat, lon = WaypointPlanner._offset_gps(
                    prev.latitude, prev.longitude, n_off, e_off
                )
                waypoints.append(
                    Waypoint(lat, lon, altitude_m, idx)
                )
                idx += 1

                direction = (direction + 1) % 4

            leg += expansion_m

        logger.info(
            f"Generated expanding square: {len(waypoints)} waypoints, "
            f"max radius {max_radius_m}m"
        )
        return waypoints

    @staticmethod
    def custom_waypoints(
        waypoint_dicts: List[dict], altitude_m: float
    ) -> List[Waypoint]:
        """Create waypoints from a list of coordinate dicts.

        Args:
            waypoint_dicts: List of {"lat": float, "lon": float} dicts
            altitude_m: Default altitude if not specified per waypoint

        Returns:
            List of Waypoint objects.
        """
        waypoints = []
        for i, wp in enumerate(waypoint_dicts):
            waypoints.append(
                Waypoint(
                    latitude=wp["lat"],
                    longitude=wp["lon"],
                    altitude=wp.get("alt", altitude_m),
                    index=i,
                )
            )

        logger.info(f"Loaded {len(waypoints)} custom waypoints")
        return waypoints

    @staticmethod
    def _offset_gps(
        lat: float, lon: float, north_m: float, east_m: float
    ) -> tuple[float, float]:
        """Offset a GPS coordinate by meters North and East.

        Args:
            lat: Starting latitude (degrees)
            lon: Starting longitude (degrees)
            north_m: North offset in meters
            east_m: East offset in meters

        Returns:
            Tuple of (new_lat, new_lon) in degrees.
        """
        lat_offset = north_m / EARTH_RADIUS_M * (180 / math.pi)
        lon_offset = east_m / (
            EARTH_RADIUS_M * math.cos(math.radians(lat))
        ) * (180 / math.pi)
        return lat + lat_offset, lon + lon_offset
