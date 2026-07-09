"""
Geotagging — Project pixel detections to GPS coordinates.

Uses the drone's GPS position, altitude, heading, and camera intrinsics
to estimate the ground-plane GPS location of each detection.
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from src.perception.tracker import Track

logger = logging.getLogger(__name__)

# Earth radius in meters (WGS84 approximation)
EARTH_RADIUS_M = 6_371_000.0


@dataclass
class GeotaggedDetection:
    """A tracked detection with estimated GPS coordinates."""
    track_id: int
    class_name: str
    confidence: float
    bbox: np.ndarray          # [x1, y1, x2, y2] in pixels
    pixel_center: tuple[int, int]
    latitude_deg: float       # Estimated ground GPS
    longitude_deg: float
    drone_altitude_m: float
    timestamp: float


class GPSGeotagger:
    """Projects pixel coordinates to GPS using pinhole camera model.

    Assumes:
    - Downward-facing (nadir) camera
    - Flat ground plane
    - Known camera field of view and image dimensions
    """

    def __init__(
        self,
        camera_hfov_deg: float = 60.0,
        image_width: int = 640,
        image_height: int = 480,
    ):
        self._hfov_rad = math.radians(camera_hfov_deg)
        self._img_w = image_width
        self._img_h = image_height

        # Compute vertical FOV from aspect ratio
        aspect = image_height / image_width
        self._vfov_rad = 2.0 * math.atan(
            aspect * math.tan(self._hfov_rad / 2.0)
        )

        logger.info(
            f"Geotagger initialized: HFOV={camera_hfov_deg}°, "
            f"VFOV={math.degrees(self._vfov_rad):.1f}°, "
            f"image={image_width}x{image_height}"
        )

    def pixel_to_gps(
        self,
        pixel_x: int,
        pixel_y: int,
        drone_lat: float,
        drone_lon: float,
        drone_alt: float,
        drone_heading_deg: float,
    ) -> Tuple[float, float]:
        """Convert pixel coordinates to GPS coordinates.

        Projects the pixel through the camera frustum onto the ground plane,
        then offsets from the drone's GPS position.

        Args:
            pixel_x: Pixel X coordinate (0 = left)
            pixel_y: Pixel Y coordinate (0 = top)
            drone_lat: Drone latitude in degrees
            drone_lon: Drone longitude in degrees
            drone_alt: Drone altitude above ground in meters
            drone_heading_deg: Drone heading (0=North, 90=East)

        Returns:
            Tuple of (latitude_deg, longitude_deg) of the ground point.
        """
        if drone_alt <= 0:
            return drone_lat, drone_lon

        # Normalize pixel to [-1, 1] relative to image center
        norm_x = (pixel_x - self._img_w / 2) / (self._img_w / 2)
        norm_y = (pixel_y - self._img_h / 2) / (self._img_h / 2)

        # Convert to angular offset from nadir
        angle_x = norm_x * (self._hfov_rad / 2)
        angle_y = norm_y * (self._vfov_rad / 2)

        # Ground offset in meters (flat ground approximation)
        offset_right_m = drone_alt * math.tan(angle_x)
        offset_forward_m = -drone_alt * math.tan(angle_y)  # Negative because y-axis is inverted

        # Rotate by heading to get North/East offsets
        heading_rad = math.radians(drone_heading_deg)
        offset_north_m = (
            offset_forward_m * math.cos(heading_rad)
            - offset_right_m * math.sin(heading_rad)
        )
        offset_east_m = (
            offset_forward_m * math.sin(heading_rad)
            + offset_right_m * math.cos(heading_rad)
        )

        # Convert meter offsets to GPS degrees
        lat_offset = offset_north_m / EARTH_RADIUS_M * (180 / math.pi)
        lon_offset = offset_east_m / (
            EARTH_RADIUS_M * math.cos(math.radians(drone_lat))
        ) * (180 / math.pi)

        return drone_lat + lat_offset, drone_lon + lon_offset

    def tag_detections(
        self,
        tracks: List[Track],
        drone_lat: float,
        drone_lon: float,
        drone_alt: float,
        drone_heading_deg: float,
        timestamp: float,
    ) -> List[GeotaggedDetection]:
        """Add GPS coordinates to each tracked detection.

        Args:
            tracks: List of Track objects from the tracker
            drone_lat: Current drone latitude
            drone_lon: Current drone longitude
            drone_alt: Current altitude above ground (meters)
            drone_heading_deg: Current heading
            timestamp: Frame timestamp

        Returns:
            List of GeotaggedDetection objects
        """
        geotagged = []

        for track in tracks:
            cx, cy = track.center
            lat, lon = self.pixel_to_gps(
                cx, cy, drone_lat, drone_lon, drone_alt, drone_heading_deg
            )

            geotagged.append(
                GeotaggedDetection(
                    track_id=track.track_id,
                    class_name=track.class_name,
                    confidence=track.confidence,
                    bbox=track.bbox,
                    pixel_center=(cx, cy),
                    latitude_deg=lat,
                    longitude_deg=lon,
                    drone_altitude_m=drone_alt,
                    timestamp=timestamp,
                )
            )

        return geotagged
