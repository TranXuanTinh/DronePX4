"""
MAVLink Bridge — MAVSDK implementation of DroneConnector.

Handles connection lifecycle, health monitoring, and provides
telemetry streaming via the MAVSDK async Python API.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Callable, Awaitable

from mavsdk import System

from src.core.interfaces import DroneConnector
from src.core.types import TelemetryFrame, Position, Attitude

logger = logging.getLogger(__name__)


class MAVLinkBridge(DroneConnector):
    """MAVSDK-based drone connector for PX4 SITL.

    Implements the DroneConnector interface so consumers can depend
    on the abstraction rather than this concrete class.

    Usage:
        async with MAVLinkBridge() as bridge:
            await bridge.wait_for_ready()
            telem = bridge.latest_telemetry
    """

    SITL_ADDRESS = "udp://:14540"

    def __init__(self, connection_string: Optional[str] = None) -> None:
        self._address = connection_string or self.SITL_ADDRESS
        self._drone = System()
        self._connected = False
        self._latest_telemetry: Optional[TelemetryFrame] = None
        self._telemetry_task: Optional[asyncio.Task] = None

    # ── DroneConnector interface ─────────────────────────────

    async def connect(self) -> None:
        """Connect to PX4 SITL via UDP."""
        logger.info(f"Connecting to PX4 SITL at {self._address}...")
        await self._drone.connect(system_address=self._address)

        async for state in self._drone.core.connection_state():
            if state.is_connected:
                self._connected = True
                logger.info("Connected to PX4 SITL")
                break

    async def disconnect(self) -> None:
        """Cleanup and disconnect."""
        await self.stop_telemetry_stream()
        self._connected = False
        logger.info("Disconnected from PX4 SITL")

    async def wait_for_ready(self, timeout: float = 60.0) -> None:
        """Wait for vehicle health checks to pass (GPS fix, home position)."""
        logger.info("Waiting for vehicle to be ready...")
        try:
            async for health in self._drone.telemetry.health():
                if health.is_global_position_ok and health.is_home_position_ok:
                    logger.info("Vehicle is ready (GPS OK, Home position set)")
                    return
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Vehicle did not become ready within {timeout}s. "
                "Ensure PX4 SITL is running with GPS simulation."
            )

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def latest_telemetry(self) -> Optional[TelemetryFrame]:
        return self._latest_telemetry

    async def start_telemetry_stream(
        self, rate_hz: float = 10.0, callback=None,
    ) -> None:
        """Start background telemetry collection at specified rate."""
        await self._drone.telemetry.set_rate_position(rate_hz)
        await self._drone.telemetry.set_rate_attitude_euler(rate_hz)
        await self._drone.telemetry.set_rate_battery(1.0)
        await self._drone.telemetry.set_rate_gps_info(1.0)

        self._telemetry_task = asyncio.create_task(
            self._telemetry_loop(callback)
        )
        logger.info(f"Telemetry stream started at {rate_hz} Hz")

    async def stop_telemetry_stream(self) -> None:
        """Stop the background telemetry collection."""
        if self._telemetry_task:
            self._telemetry_task.cancel()
            try:
                await self._telemetry_task
            except asyncio.CancelledError:
                pass
            self._telemetry_task = None

    # ── Context manager ──────────────────────────────────────

    async def __aenter__(self) -> MAVLinkBridge:
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.disconnect()

    # ── MAVSDK-specific accessors (not in the interface) ─────

    @property
    def drone(self) -> System:
        """Access the underlying MAVSDK System object."""
        return self._drone

    # ── Private ──────────────────────────────────────────────

    async def _telemetry_loop(self, callback=None) -> None:
        """Internal telemetry collection loop."""
        # Cache latest values from each stream
        position = Position(0, 0, 0, 0)
        attitude = Attitude(0, 0, 0)
        heading = 0.0
        speed = 0.0
        battery_pct = 100.0
        battery_v = 0.0
        flight_mode = "UNKNOWN"
        armed = False
        gps_sats = 0
        gps_fix = 0

        async def _update_position():
            nonlocal position
            async for pos in self._drone.telemetry.position():
                position = Position(
                    pos.latitude_deg, pos.longitude_deg,
                    pos.absolute_altitude_m, pos.relative_altitude_m,
                )

        async def _update_attitude():
            nonlocal attitude
            async for att in self._drone.telemetry.attitude_euler():
                attitude = Attitude(att.roll_deg, att.pitch_deg, att.yaw_deg)

        async def _update_heading():
            nonlocal heading
            async for h in self._drone.telemetry.heading():
                heading = h.heading_deg

        async def _update_speed():
            nonlocal speed
            async for vel in self._drone.telemetry.velocity_ned():
                speed = (vel.north_m_s ** 2 + vel.east_m_s ** 2) ** 0.5

        async def _update_battery():
            nonlocal battery_pct, battery_v
            async for bat in self._drone.telemetry.battery():
                battery_pct = bat.remaining_percent
                battery_v = bat.voltage_v

        async def _update_flight_mode():
            nonlocal flight_mode
            async for mode in self._drone.telemetry.flight_mode():
                flight_mode = str(mode)

        async def _update_armed():
            nonlocal armed
            async for a in self._drone.telemetry.armed():
                armed = a

        async def _update_gps():
            nonlocal gps_sats, gps_fix
            async for info in self._drone.telemetry.gps_info():
                gps_sats = info.num_satellites
                gps_fix = info.fix_type.value

        tasks = [
            asyncio.create_task(coro())
            for coro in (
                _update_position, _update_attitude, _update_heading,
                _update_speed, _update_battery, _update_flight_mode,
                _update_armed, _update_gps,
            )
        ]

        try:
            while True:
                frame = TelemetryFrame(
                    timestamp=time.time(),
                    position=position,
                    attitude=attitude,
                    heading_deg=heading,
                    groundspeed_ms=speed,
                    battery_percent=battery_pct,
                    battery_voltage=battery_v,
                    flight_mode=flight_mode,
                    armed=armed,
                    is_connected=self._connected,
                    gps_num_satellites=gps_sats,
                    gps_fix_type=gps_fix,
                )
                self._latest_telemetry = frame

                if callback:
                    await callback(frame)

                await asyncio.sleep(0.1)  # 10 Hz

        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            logger.info("Telemetry stream stopped")
