"""
Safety Monitor — Checks simulated safety conditions.

Monitors battery, geofence, altitude, and connection status.
Returns the highest-priority safety action when triggered.
"""
from __future__ import annotations

import logging
import math
from enum import IntEnum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.bridge.mavlink_bridge import TelemetryFrame

logger = logging.getLogger(__name__)


class SafetyAction(IntEnum):
    """Safety actions ordered by priority (higher = more urgent)."""
    NONE = 0
    WARN = 1
    RTL_NOW = 2
    EMERGENCY_LAND = 3


class SafetyMonitor:
    """Monitors simulated safety conditions.

    Checks battery level, geofence boundary, altitude limit,
    and SITL connection health.
    """

    def __init__(
        self,
        geofence_radius_m: float = 500.0,
        max_altitude_m: float = 120.0,
        min_battery_pct: float = 20.0,
        critical_battery_pct: float = 10.0,
        home_lat: float = 47.397742,
        home_lon: float = 8.545594,
    ):
        self._geofence_radius = geofence_radius_m
        self._max_altitude = max_altitude_m
        self._min_battery = min_battery_pct
        self._critical_battery = critical_battery_pct
        self._home_lat = home_lat
        self._home_lon = home_lon

    def check(self, telemetry: TelemetryFrame) -> SafetyAction:
        """Run all safety checks. Returns highest-priority action.

        Args:
            telemetry: Current telemetry frame

        Returns:
            SafetyAction indicating required response
        """
        actions = [
            self._check_battery(telemetry.battery_percent),
            self._check_geofence(
                telemetry.position.latitude_deg,
                telemetry.position.longitude_deg,
            ),
            self._check_altitude(telemetry.position.relative_altitude_m),
            self._check_connection(telemetry.is_connected),
        ]

        return max(actions)

    def _check_battery(self, percent: float) -> SafetyAction:
        """Check battery level."""
        if percent <= 0:
            return SafetyAction.NONE  # Battery data not available

        if percent < self._critical_battery:
            logger.warning(f"CRITICAL battery: {percent:.1f}%")
            return SafetyAction.EMERGENCY_LAND

        if percent < self._min_battery:
            logger.warning(f"Low battery: {percent:.1f}%")
            return SafetyAction.RTL_NOW

        return SafetyAction.NONE

    def _check_geofence(self, lat: float, lon: float) -> SafetyAction:
        """Check if drone is within geofence radius from home."""
        dist = self._haversine_distance(
            self._home_lat, self._home_lon, lat, lon
        )

        if dist > self._geofence_radius:
            logger.warning(
                f"GEOFENCE breach: {dist:.0f}m from home "
                f"(limit: {self._geofence_radius:.0f}m)"
            )
            return SafetyAction.RTL_NOW

        if dist > self._geofence_radius * 0.9:
            logger.info(f"Approaching geofence: {dist:.0f}m from home")
            return SafetyAction.WARN

        return SafetyAction.NONE

    def _check_altitude(self, altitude_m: float) -> SafetyAction:
        """Check altitude limit."""
        if altitude_m > self._max_altitude:
            logger.warning(
                f"Altitude limit exceeded: {altitude_m:.1f}m "
                f"(max: {self._max_altitude:.1f}m)"
            )
            return SafetyAction.RTL_NOW

        if altitude_m > self._max_altitude * 0.9:
            return SafetyAction.WARN

        return SafetyAction.NONE

    def _check_connection(self, is_connected: bool) -> SafetyAction:
        """Check SITL connection."""
        if not is_connected:
            logger.warning("Lost connection to PX4 SITL")
            return SafetyAction.RTL_NOW

        return SafetyAction.NONE

    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two GPS points in meters."""
        R = 6_371_000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
