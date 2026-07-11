"""
Safety Monitor — Chain of Responsibility pattern.

Each safety concern is a separate SafetyRule. SafetyMonitor composes
them and returns the highest-priority action. Adding a new rule
(e.g., wind speed) requires only creating a new class — no existing
code changes (OCP).
"""
from __future__ import annotations

import logging
import math
from typing import List

from src.core.interfaces import SafetyChecker, SafetyRule
from src.core.types import SafetyAction, TelemetryFrame
from src.core.geo import haversine_distance

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Concrete Safety Rules
# ──────────────────────────────────────────────────────────────

class BatteryRule(SafetyRule):
    """Check battery level against thresholds."""

    def __init__(
        self, min_pct: float = 20.0, critical_pct: float = 10.0,
    ) -> None:
        self._min_pct = min_pct
        self._critical_pct = critical_pct

    @property
    def name(self) -> str:
        return "battery"

    def evaluate(self, telemetry: TelemetryFrame) -> SafetyAction:
        pct = telemetry.battery_percent
        if pct <= 0:
            return SafetyAction.NONE  # Data not available

        if pct < self._critical_pct:
            logger.warning(f"CRITICAL battery: {pct:.1f}%")
            return SafetyAction.EMERGENCY_LAND

        if pct < self._min_pct:
            logger.warning(f"Low battery: {pct:.1f}%")
            return SafetyAction.RTL_NOW

        return SafetyAction.NONE


class GeofenceRule(SafetyRule):
    """Check if drone is within geofence radius from home."""

    def __init__(
        self,
        home_lat: float,
        home_lon: float,
        radius_m: float = 500.0,
    ) -> None:
        self._home_lat = home_lat
        self._home_lon = home_lon
        self._radius_m = radius_m

    @property
    def name(self) -> str:
        return "geofence"

    def evaluate(self, telemetry: TelemetryFrame) -> SafetyAction:
        dist = haversine_distance(
            self._home_lat, self._home_lon,
            telemetry.position.latitude_deg,
            telemetry.position.longitude_deg,
        )

        if dist > self._radius_m:
            logger.warning(
                f"GEOFENCE breach: {dist:.0f}m from home "
                f"(limit: {self._radius_m:.0f}m)"
            )
            return SafetyAction.RTL_NOW

        if dist > self._radius_m * 0.9:
            logger.info(f"Approaching geofence: {dist:.0f}m from home")
            return SafetyAction.WARN

        return SafetyAction.NONE


class AltitudeRule(SafetyRule):
    """Check altitude limit."""

    def __init__(self, max_altitude_m: float = 120.0) -> None:
        self._max_altitude = max_altitude_m

    @property
    def name(self) -> str:
        return "altitude"

    def evaluate(self, telemetry: TelemetryFrame) -> SafetyAction:
        alt = telemetry.position.relative_altitude_m

        if alt > self._max_altitude:
            logger.warning(
                f"Altitude limit exceeded: {alt:.1f}m "
                f"(max: {self._max_altitude:.1f}m)"
            )
            return SafetyAction.RTL_NOW

        if alt > self._max_altitude * 0.9:
            return SafetyAction.WARN

        return SafetyAction.NONE


class ConnectionRule(SafetyRule):
    """Check SITL connection."""

    @property
    def name(self) -> str:
        return "connection"

    def evaluate(self, telemetry: TelemetryFrame) -> SafetyAction:
        if not telemetry.is_connected:
            logger.warning("Lost connection to PX4 SITL")
            return SafetyAction.RTL_NOW
        return SafetyAction.NONE


# ──────────────────────────────────────────────────────────────
# Composite SafetyMonitor
# ──────────────────────────────────────────────────────────────

class SafetyMonitor(SafetyChecker):
    """Composite safety checker — runs all rules, returns worst action.

    Implements the Chain of Responsibility pattern. New rules are
    added via `add_rule()` — no existing code changes (OCP).

    Usage:
        monitor = SafetyMonitor.from_config(config)
        action = monitor.check(telemetry_frame)
    """

    def __init__(self) -> None:
        self._rules: List[SafetyRule] = []

    # ── SafetyChecker interface ──────────────────────────────

    def check(self, telemetry: TelemetryFrame) -> SafetyAction:
        """Run all rules. Return the highest-priority action."""
        return max(
            (rule.evaluate(telemetry) for rule in self._rules),
            default=SafetyAction.NONE,
        )

    def add_rule(self, rule: SafetyRule) -> None:
        self._rules.append(rule)
        logger.debug(f"Safety rule added: {rule.name}")

    # ── Factory ──────────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        geofence_radius_m: float = 500.0,
        max_altitude_m: float = 120.0,
        min_battery_pct: float = 20.0,
        critical_battery_pct: float = 10.0,
        home_lat: float = 47.397742,
        home_lon: float = 8.545594,
    ) -> SafetyMonitor:
        """Create a SafetyMonitor with the standard rule set.

        This factory method provides backward compatibility with the
        old constructor signature.
        """
        monitor = cls()
        monitor.add_rule(BatteryRule(min_battery_pct, critical_battery_pct))
        monitor.add_rule(GeofenceRule(home_lat, home_lon, geofence_radius_m))
        monitor.add_rule(AltitudeRule(max_altitude_m))
        monitor.add_rule(ConnectionRule())
        return monitor
