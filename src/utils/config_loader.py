"""
Config Loader — Load and validate YAML configuration.
"""

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "vehicle" / "sim_config.yaml"


def load_config(path: Optional[str] = None) -> dict[str, Any]:
    """Load YAML configuration file.

    Args:
        path: Path to config file. Defaults to config/vehicle/sim_config.yaml

    Returns:
        Configuration dictionary.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return _default_config()

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    logger.info(f"Configuration loaded from {config_path}")
    return config


def _default_config() -> dict[str, Any]:
    """Return default configuration if no file is found."""
    return {
        "vehicle": {"name": "Inspector-SIM", "frame": "x500"},
        "connection": {"mavsdk_address": "udp://:14540"},
        "camera": {
            "source": "gazebo", "width": 640, "height": 480,
            "hfov_deg": 60, "fps": 15,
        },
        "perception": {
            "model": "yolov8s.pt", "backend": "pytorch",
            "device": "cpu", "confidence_threshold": 0.45,
            "classes": ["person", "car", "truck"],
            "tracker": {
                "track_thresh": 0.5, "match_thresh": 0.8,
                "track_buffer": 30, "frame_rate": 10,
            },
        },
        "mission": {
            "takeoff_altitude_m": 15.0, "search_altitude_m": 20.0,
            "inspect_altitude_m": 8.0, "max_speed_ms": 5.0,
            "search_area": {
                "center_lat": 47.397742, "center_lon": 8.545594,
                "width_m": 200, "height_m": 150, "spacing_m": 30,
            },
            "search_pattern": "lawnmower",
            "detection_confirm_frames": 5,
        },
        "safety": {
            "geofence_radius_m": 500, "max_altitude_m": 120,
            "min_battery_percent": 20, "critical_battery_percent": 10,
        },
        "dashboard": {
            "backend_host": "0.0.0.0", "backend_port": 8000,
            "frontend_port": 3000, "video_quality": 70,
            "telemetry_rate_hz": 10,
        },
        "logging": {
            "level": "INFO", "log_dir": "data/logs",
            "detection_dir": "data/detections",
            "report_dir": "data/reports",
        },
    }
