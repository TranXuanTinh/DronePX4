"""
Failsafe test fixtures — shared across all failsafe scenario tests.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.core.types import SafetyAction
from src.mission.safety import SafetyMonitor


@pytest.fixture
def safety_monitor():
    """Pre-configured SafetyMonitor with default rules."""
    return SafetyMonitor.from_config(
        geofence_radius_m=500.0,
        max_altitude_m=120.0,
        min_battery_pct=20.0,
        critical_battery_pct=10.0,
        home_lat=47.397742,
        home_lon=8.545594,
    )


@pytest.fixture
def custom_safety_monitor():
    """Factory for SafetyMonitor with custom parameters."""
    def _factory(
        geofence_radius_m=500.0,
        max_altitude_m=120.0,
        min_battery_pct=20.0,
        critical_battery_pct=10.0,
        home_lat=47.397742,
        home_lon=8.545594,
    ):
        return SafetyMonitor.from_config(
            geofence_radius_m=geofence_radius_m,
            max_altitude_m=max_altitude_m,
            min_battery_pct=min_battery_pct,
            critical_battery_pct=critical_battery_pct,
            home_lat=home_lat,
            home_lon=home_lon,
        )
    return _factory
