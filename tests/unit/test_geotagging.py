"""
Unit tests for GPSGeotagger — Geotagger implementation.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.types import Track, GeotaggedDetection
from src.perception.geotagging import GPSGeotagger


def _make_track(cx=320, cy=240, track_id=1):
    """Create a Track with bounding box centered at (cx, cy)."""
    half_w, half_h = 40, 30
    return Track(
        track_id=track_id,
        bbox=np.array([cx - half_w, cy - half_h, cx + half_w, cy + half_h]),
        class_id=0,
        class_name="car",
        confidence=0.9,
        age=5,
        is_confirmed=True,
    )


class TestGPSGeotagger:
    """Test GPS geotagging from pixel coordinates."""

    def test_center_pixel_maps_to_drone_position(self, geotagger=None):
        g = geotagger or GPSGeotagger(60.0, 640, 480)
        lat, lon = g.pixel_to_gps(320, 240, 47.3977, 8.5456, 20.0, 0.0)
        assert abs(lat - 47.3977) < 0.0001
        assert abs(lon - 8.5456) < 0.0001

    def test_right_pixel_maps_east(self, geotagger=None):
        g = geotagger or GPSGeotagger(60.0, 640, 480)
        lat_c, lon_c = g.pixel_to_gps(320, 240, 47.3977, 8.5456, 20.0, 0.0)
        lat_r, lon_r = g.pixel_to_gps(600, 240, 47.3977, 8.5456, 20.0, 0.0)
        assert lon_r > lon_c

    def test_top_pixel_maps_north(self, geotagger=None):
        g = geotagger or GPSGeotagger(60.0, 640, 480)
        lat_c, _ = g.pixel_to_gps(320, 240, 47.3977, 8.5456, 20.0, 0.0)
        lat_t, _ = g.pixel_to_gps(320, 50, 47.3977, 8.5456, 20.0, 0.0)
        assert lat_t > lat_c

    def test_zero_altitude_returns_drone_position(self, geotagger=None):
        g = geotagger or GPSGeotagger(60.0, 640, 480)
        lat, lon = g.pixel_to_gps(100, 100, 47.3977, 8.5456, 0.0, 0.0)
        assert lat == 47.3977
        assert lon == 8.5456

    def test_higher_altitude_wider_offset(self, geotagger=None):
        g = geotagger or GPSGeotagger(60.0, 640, 480)
        _, lon_low = g.pixel_to_gps(600, 240, 47.3977, 8.5456, 10.0, 0.0)
        _, lon_high = g.pixel_to_gps(600, 240, 47.3977, 8.5456, 50.0, 0.0)
        assert abs(lon_high - 8.5456) > abs(lon_low - 8.5456)

    def test_heading_rotation(self, geotagger=None):
        g = geotagger or GPSGeotagger(60.0, 640, 480)
        lat_n, lon_n = g.pixel_to_gps(320, 50, 47.3977, 8.5456, 20.0, 0.0)
        lat_e, lon_e = g.pixel_to_gps(320, 50, 47.3977, 8.5456, 20.0, 90.0)
        assert lat_n > lat_e or lon_e > lon_n

    def test_tag_detections_returns_geotagged_list(self, geotagger=None):
        g = geotagger or GPSGeotagger(60.0, 640, 480)
        tracks = [_make_track(320, 240, 1), _make_track(500, 100, 2)]
        result = g.tag_detections(tracks, 47.3977, 8.5456, 20.0, 0.0, 1000.0)
        assert len(result) == 2
        assert isinstance(result[0], GeotaggedDetection)
        assert result[0].track_id == 1
        assert result[1].track_id == 2
