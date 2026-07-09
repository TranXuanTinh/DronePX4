"""
MAVLink Bridge — MAVSDK connection manager for PX4 SITL.

Handles connection lifecycle, health monitoring, and provides
the core drone System object to other modules.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from mavsdk import System
from mavsdk.core import ConnectionState

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """GPS position data."""
    latitude_deg: float
    longitude_deg: float
    absolute_altitude_m: float
    relative_altitude_m: float


@dataclass
class Attitude:
    """Vehicle attitude (Euler angles)."""
    roll_deg: float
    pitch_deg: float
    yaw_deg: float


@dataclass
class TelemetryFrame:
    """Aggregated telemetry snapshot."""
    timestamp: float
    position: Position
    attitude: Attitude
    heading_deg: float
    groundspeed_ms: float
    battery_percent: float
    battery_voltage: float
    flight_mode: str
    armed: bool
    is_connected: bool
    gps_num_satellites: int
    gps_fix_type: int


class MAVLinkBridge:
    """Manages MAVSDK connection to PX4 SITL.

    Usage:
        bridge = MAVLinkBridge()
        await bridge.connect()
        await bridge.wait_for_ready()
        position = await bridge.get_position()
    """

    SITL_ADDRESS = "udp://:14540"

    def __init__(self, connection_string: Optional[str] = None):
        self._address = connection_string or self.SITL_ADDRESS
        self._drone = System()
        self._connected = False
        self._latest_telemetry: Optional[TelemetryFrame] = None
        self._telemetry_task: Optional[asyncio.Task] = None

    @property
    def drone(self) -> System:
        """Access the underlying MAVSDK System object."""
        return self._drone

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def latest_telemetry(self) -> Optional[TelemetryFrame]:
        return self._latest_telemetry

    async def connect(self) -> None:
        """Connect to PX4 SITL via UDP."""
        logger.info(f"Connecting to PX4 SITL at {self._address}...")
        await self._drone.connect(system_address=self._address)

        # Wait for connection
        async for state in self._drone.core.connection_state():
            if state.is_connected:
                self._connected = True
                logger.info("Connected to PX4 SITL")
                break

    async def wait_for_ready(self, timeout: float = 60.0) -> None:
        """Wait for vehicle health checks to pass (GPS fix, home position)."""
        logger.info("Waiting for vehicle to be ready...")

        try:
            ready = False
            async for health in self._drone.telemetry.health():
                if health.is_global_position_ok and health.is_home_position_ok:
                    ready = True
                    break

            if ready:
                logger.info("Vehicle is ready (GPS OK, Home position set)")
            else:
                raise TimeoutError("Vehicle did not become ready")

        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Vehicle did not become ready within {timeout}s. "
                "Ensure PX4 SITL is running with GPS simulation."
            )

    async def get_position(self) -> Position:
        """Get current GPS position (single read)."""
        async for pos in self._drone.telemetry.position():
            return Position(
                latitude_deg=pos.latitude_deg,
                longitude_deg=pos.longitude_deg,
                absolute_altitude_m=pos.absolute_altitude_m,
                relative_altitude_m=pos.relative_altitude_m,
            )

    async def get_heading(self) -> float:
        """Get current heading in degrees."""
        async for heading in self._drone.telemetry.heading():
            return heading.heading_deg

    async def get_battery(self) -> tuple[float, float]:
        """Get battery (remaining_percent, voltage_v)."""
        async for battery in self._drone.telemetry.battery():
            return battery.remaining_percent, battery.voltage_v

    async def get_flight_mode(self) -> str:
        """Get current flight mode as string."""
        async for mode in self._drone.telemetry.flight_mode():
            return str(mode)

    async def get_armed(self) -> bool:
        """Check if vehicle is armed."""
        async for armed in self._drone.telemetry.armed():
            return armed

    async def start_telemetry_stream(
        self, rate_hz: float = 10.0, callback=None
    ) -> None:
        """Start background telemetry collection at specified rate.

        Args:
            rate_hz: Telemetry update rate (default 10 Hz)
            callback: Optional async callback(TelemetryFrame) on each update
        """
        # Set telemetry rates
        await self._drone.telemetry.set_rate_position(rate_hz)
        await self._drone.telemetry.set_rate_attitude_euler(rate_hz)
        await self._drone.telemetry.set_rate_battery(1.0)  # Battery at 1 Hz
        await self._drone.telemetry.set_rate_gps_info(1.0)

        self._telemetry_task = asyncio.create_task(
            self._telemetry_loop(callback)
        )
        logger.info(f"Telemetry stream started at {rate_hz} Hz")

    async def _telemetry_loop(self, callback=None) -> None:
        """Internal telemetry collection loop."""
        import time

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
                attitude = Attitude(
                    att.roll_deg, att.pitch_deg, att.yaw_deg
                )

        async def _update_heading():
            nonlocal heading
            async for h in self._drone.telemetry.heading():
                heading = h.heading_deg

        async def _update_speed():
            nonlocal speed
            async for vel in self._drone.telemetry.velocity_ned():
                speed = (vel.north_m_s**2 + vel.east_m_s**2) ** 0.5

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

        # Start all telemetry subscriptions as background tasks
        tasks = [
            asyncio.create_task(_update_position()),
            asyncio.create_task(_update_attitude()),
            asyncio.create_task(_update_heading()),
            asyncio.create_task(_update_speed()),
            asyncio.create_task(_update_battery()),
            asyncio.create_task(_update_flight_mode()),
            asyncio.create_task(_update_armed()),
            asyncio.create_task(_update_gps()),
        ]

        try:
            # Aggregate and publish at target rate
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

    async def stop_telemetry_stream(self) -> None:
        """Stop the background telemetry collection."""
        if self._telemetry_task:
            self._telemetry_task.cancel()
            try:
                await self._telemetry_task
            except asyncio.CancelledError:
                pass
            self._telemetry_task = None

    async def disconnect(self) -> None:
        """Cleanup and disconnect."""
        await self.stop_telemetry_stream()
        self._connected = False
        logger.info("Disconnected from PX4 SITL")
