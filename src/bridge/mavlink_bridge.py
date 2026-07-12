"""
MAVLink Bridge — MAVSDK implementation of DroneConnector.

Handles connection lifecycle, health monitoring, and provides
telemetry streaming via the MAVSDK async Python API.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
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
    MAVSDK_PORT = 50051
    MAX_CONNECT_RETRIES = 3
    CONNECT_RETRY_DELAY = 2.0

    def __init__(self, connection_string: Optional[str] = None) -> None:
        self._address = connection_string or self.SITL_ADDRESS
        self._drone: Optional[System] = None
        self._connected = False
        self._latest_telemetry: Optional[TelemetryFrame] = None
        self._telemetry_task: Optional[asyncio.Task] = None
        self._reconnecting = False

    # ── DroneConnector interface ─────────────────────────────

    async def connect(self) -> None:
        """Connect to PX4 SITL via UDP with retry logic."""
        last_error = None

        for attempt in range(1, self.MAX_CONNECT_RETRIES + 1):
            try:
                logger.info(
                    f"Connecting to PX4 SITL at {self._address} "
                    f"(attempt {attempt}/{self.MAX_CONNECT_RETRIES})..."
                )

                # Clean up any orphaned mavsdk_server processes
                self._kill_orphaned_mavsdk_server()

                # Create a fresh System instance for each attempt
                self._drone = System()
                await self._drone.connect(system_address=self._address)

                # Wait for actual connection with a timeout
                connected = await asyncio.wait_for(
                    self._wait_for_connection(), timeout=15.0,
                )
                if connected:
                    self._connected = True
                    logger.info("Connected to PX4 SITL")
                    return

            except asyncio.TimeoutError:
                last_error = TimeoutError(
                    f"Connection attempt {attempt} timed out"
                )
                logger.warning(f"Connection attempt {attempt} timed out")
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Connection attempt {attempt} failed: {e}"
                )

            if attempt < self.MAX_CONNECT_RETRIES:
                delay = self.CONNECT_RETRY_DELAY * attempt
                logger.info(f"Retrying in {delay:.0f}s...")
                await asyncio.sleep(delay)

        raise ConnectionError(
            f"Failed to connect after {self.MAX_CONNECT_RETRIES} attempts. "
            f"Last error: {last_error}"
        )

    async def _wait_for_connection(self) -> bool:
        """Wait for the drone connection state to become connected."""
        async for state in self._drone.core.connection_state():
            if state.is_connected:
                return True
        return False

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

    # ── Connection Health ────────────────────────────────────

    async def is_healthy(self) -> bool:
        """Check if the gRPC channel to mavsdk_server is alive."""
        if not self._drone or not self._connected:
            return False
        try:
            # Quick gRPC round-trip to test the channel
            async for state in self._drone.core.connection_state():
                return state.is_connected
        except Exception:
            return False
        return False

    async def reconnect(self) -> bool:
        """Attempt to reconnect to the drone.

        Returns True if reconnection succeeded, False otherwise.
        Thread-safe: prevents concurrent reconnection attempts.
        """
        if self._reconnecting:
            logger.debug("Reconnection already in progress, skipping")
            return False

        self._reconnecting = True
        try:
            logger.warning("Attempting reconnection to PX4 SITL...")
            self._connected = False

            # Stop old telemetry
            if self._telemetry_task:
                self._telemetry_task.cancel()
                try:
                    await self._telemetry_task
                except asyncio.CancelledError:
                    pass
                self._telemetry_task = None

            # Reconnect
            await self.connect()
            await self.wait_for_ready(timeout=30.0)
            logger.info("Reconnection successful")
            return True
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return False
        finally:
            self._reconnecting = False

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

    @staticmethod
    def _kill_orphaned_mavsdk_server() -> None:
        """Kill any orphaned mavsdk_server processes on port 50051.

        This prevents port conflicts when the backend restarts
        (e.g., uvicorn --reload).
        """
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{MAVLinkBridge.MAVSDK_PORT}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split("\n")
                for pid_str in pids:
                    try:
                        pid = int(pid_str.strip())
                        # Don't kill our own process
                        if pid != os.getpid():
                            os.kill(pid, signal.SIGTERM)
                            logger.info(
                                f"Killed orphaned mavsdk_server "
                                f"(PID {pid}) on port {MAVLinkBridge.MAVSDK_PORT}"
                            )
                    except (ValueError, ProcessLookupError, PermissionError):
                        pass
                # Give processes time to die
                import time as _time
                _time.sleep(0.5)
        except FileNotFoundError:
            # lsof not available — try fuser instead
            try:
                subprocess.run(
                    ["fuser", "-k", f"{MAVLinkBridge.MAVSDK_PORT}/tcp"],
                    capture_output=True, timeout=5,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        except subprocess.TimeoutExpired:
            pass

    async def _telemetry_loop(self, callback=None) -> None:
        """Internal telemetry collection loop with error recovery."""
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

        async def _run_with_recovery(coro_factory, name: str):
            """Run a telemetry stream coroutine with automatic recovery."""
            while True:
                try:
                    await coro_factory()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(
                        f"Telemetry stream '{name}' error: {e}. "
                        "Will retry in 2s..."
                    )
                    await asyncio.sleep(2.0)

        tasks = [
            asyncio.create_task(_run_with_recovery(coro, name))
            for coro, name in (
                (_update_position, "position"),
                (_update_attitude, "attitude"),
                (_update_heading, "heading"),
                (_update_speed, "speed"),
                (_update_battery, "battery"),
                (_update_flight_mode, "flight_mode"),
                (_update_armed, "armed"),
                (_update_gps, "gps"),
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
