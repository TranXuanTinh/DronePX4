"""Unit tests for GPS geotagging.

Only depends on numpy (no mavsdk needed). Uses a mock Track object.
"""

import pytest
import sys
import math
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.perception.geotagging import GPSGeotagger
from src.perception.tracker import Track


class TestGPSGeotagger:

    @pytest.fixture
    def geotagger(self):
        return GPSGeotagger(
            camera_hfov_deg=60.0,
            image_width=640,
            image_height=480,
        )

    def test_center_pixel_maps_to_drone_position(self, geotagger):
        lat, lon = geotagger.pixel_to_gps(
            pixel_x=320, pixel_y=240,
            drone_lat=47.397742, drone_lon=8.545594,
            drone_alt=20.0, drone_heading_deg=0.0,
        )
        assert lat == pytest.approx(47.397742, abs=0.0001)
        assert lon == pytest.approx(8.545594, abs=0.0001)

    def test_right_pixel_maps_east(self, geotagger):
        _, center_lon = geotagger.pixel_to_gps(320, 240, 47.0, 8.0, 20.0, 0.0)
        _, right_lon = geotagger.pixel_to_gps(480, 240, 47.0, 8.0, 20.0, 0.0)
        assert right_lon > center_lon

    def test_top_pixel_maps_north(self, geotagger):
        center_lat, _ = geotagger.pixel_to_gps(320, 240, 47.0, 8.0, 20.0, 0.0)
        top_lat, _ = geotagger.pixel_to_gps(320, 120, 47.0, 8.0, 20.0, 0.0)
        assert top_lat > center_lat

    def test_higher_altitude_wider_offset(self, geotagger):
        _, lon_low = geotagger.pixel_to_gps(480, 240, 47.0, 8.0, 10.0, 0.0)
        _, lon_high = geotagger.pixel_to_gps(480, 240, 47.0, 8.0, 50.0, 0.0)
        assert abs(lon_high - 8.0) > abs(lon_low - 8.0)

    def test_zero_altitude_returns_drone_position(self, geotagger):
        lat, lon = geotagger.pixel_to_gps(480, 120, 47.0, 8.0, 0.0, 0.0)
        assert lat == 47.0
        assert lon == 8.0

    def test_heading_rotation(self, geotagger):
        _, lon_north = geotagger.pixel_to_gps(480, 240, 47.0, 8.0, 20.0, 0.0)
        lat_east, _ = geotagger.pixel_to_gps(480, 240, 47.0, 8.0, 20.0, 90.0)
        assert lat_east < 47.0

    def test_tag_detections_returns_geotagged_list(self, geotagger):
        tracks = [
            Track(
                track_id=1, bbox=np.array([300, 220, 340, 260]),
                class_id=0, class_name="car", confidence=0.9,
                age=5, is_confirmed=True,
            ),
        ]
        results = geotagger.tag_detections(tracks, 47.0, 8.0, 20.0, 0.0, 1234567890.0)
        assert len(results) == 1
        assert results[0].track_id == 1
        assert results[0].class_name == "car"
