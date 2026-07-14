"""
Flight Commands — MAVSDK implementation of FlightController.

Provides high-level async methods for common flight operations.
Depends on DroneConnector (ABC), not the concrete MAVLinkBridge.
"""
from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Optional

from mavsdk.action import ActionError
from mavsdk.offboard import (
    OffboardError,
    PositionNedYaw,
    VelocityNedYaw,
    VelocityBodyYawspeed,
)

from src.core.interfaces import FlightController, DroneConnector
from src.bridge.mavlink_bridge import MAVLinkBridge

logger = logging.getLogger(__name__)

# gRPC error types to catch for retry
try:
    from grpc.aio._call import AioRpcError
    from grpc import StatusCode
    _GRPC_AVAILABLE = True
except ImportError:
    _GRPC_AVAILABLE = False


class FlightCommands(FlightController):
    """MAVSDK-based flight command wrappers.

    Implements the FlightController interface. Accepts a DroneConnector
    but needs the MAVSDK System object for offboard commands, so it
    also accepts the concrete MAVLinkBridge for MAVSDK-specific access.

    Usage:
        cmd = FlightCommands(bridge)
        await cmd.arm()
        await cmd.takeoff(15.0)
    """

    MAX_RETRIES = 2
    RETRY_DELAY = 1.0

    def __init__(self, bridge: MAVLinkBridge) -> None:
        self._bridge = bridge
        self._drone = bridge.drone
        self._offboard_active = False

    def _refresh_drone_ref(self) -> None:
        """Refresh the MAVSDK System reference after reconnection."""
        self._drone = self._bridge.drone

    async def _with_retry(self, operation, operation_name: str):
        """Execute a drone operation with gRPC error recovery.

        If the gRPC channel is unavailable, attempts reconnection
        before retrying the operation.
        """
        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return await operation()
            except ActionError:
                raise  # Action errors are real drone errors, don't retry
            except Exception as e:
                is_grpc_unavailable = False
                if _GRPC_AVAILABLE and isinstance(e, AioRpcError):
                    is_grpc_unavailable = (
                        e.code() == StatusCode.UNAVAILABLE
                    )
                # Also catch generic connection errors
                if not is_grpc_unavailable and "UNAVAILABLE" not in str(e):
                    raise

                last_error = e
                logger.warning(
                    f"{operation_name} failed (attempt {attempt}/"
                    f"{self.MAX_RETRIES}): gRPC UNAVAILABLE — "
                    f"attempting reconnection..."
                )

                if attempt < self.MAX_RETRIES:
                    reconnected = await self._bridge.reconnect()
                    if reconnected:
                        self._refresh_drone_ref()
                        await asyncio.sleep(self.RETRY_DELAY)
                    else:
                        raise ConnectionError(
                            f"{operation_name} failed: could not "
                            f"reconnect to MAVSDK server"
                        ) from e

        raise ConnectionError(
            f"{operation_name} failed after {self.MAX_RETRIES} "
            f"retries: {last_error}"
        )

    # ── FlightController interface ───────────────────────────

    async def arm(self) -> None:
        logger.info("Arming vehicle...")
        async def _do():
            await self._drone.action.arm()
            logger.info("Vehicle armed")
        try:
            await self._with_retry(_do, "Arm")
        except ActionError as e:
            logger.error(f"Arm failed: {e}")
            raise

    async def disarm(self) -> None:
        logger.info("Disarming vehicle...")
        async def _do():
            await self._drone.action.disarm()
            logger.info("Vehicle disarmed")
        try:
            await self._with_retry(_do, "Disarm")
        except ActionError as e:
            logger.error(f"Disarm failed: {e}")
            raise

    async def takeoff(self, altitude_m: float = 15.0) -> None:
        logger.info(f"Taking off to {altitude_m}m...")
        async def _do():
            await self._drone.action.set_takeoff_altitude(altitude_m)
            await self._drone.action.takeoff()
            logger.info(f"Takeoff command sent (target: {altitude_m}m)")
        try:
            await self._with_retry(_do, "Takeoff")
        except ActionError as e:
            logger.error(f"Takeoff failed: {e}")
            raise

    async def land(self) -> None:
        logger.info("Landing...")
        async def _do():
            await self._drone.action.land()
            logger.info("Land command sent")
        try:
            await self._with_retry(_do, "Land")
        except ActionError as e:
            logger.error(f"Land failed: {e}")
            raise

    async def rtl(self) -> None:
        logger.info("Returning to launch...")
        async def _do():
            await self._drone.action.return_to_launch()
            logger.info("RTL command sent")
        try:
            await self._with_retry(_do, "RTL")
        except ActionError as e:
            logger.error(f"RTL failed: {e}")
            raise

    async def hold(self) -> None:
        logger.info("Holding position...")
        if self._offboard_active:
            await self.stop_offboard()
        async def _do():
            await self._drone.action.hold()
            logger.info("Hold command sent")
        try:
            await self._with_retry(_do, "Hold")
        except ActionError as e:
            logger.error(f"Hold failed: {e}")
            raise

    async def goto(
        self,
        latitude_deg: float,
        longitude_deg: float,
        altitude_m: float,
        yaw_deg: float = float("nan"),
    ) -> None:
        logger.info(
            f"Going to ({latitude_deg:.6f}, {longitude_deg:.6f}) "
            f"at {altitude_m:.1f}m"
        )
        async def _do():
            await self._drone.action.goto_location(
                latitude_deg, longitude_deg, altitude_m, yaw_deg,
            )
        try:
            await self._with_retry(_do, "Goto")
        except ActionError as e:
            logger.error(f"Goto failed: {e}")
            raise

    async def wait_for_altitude(
        self, target_m: float, tolerance_m: float = 1.0,
        timeout_s: float = 30.0,
    ) -> bool:
        logger.info(
            f"Waiting for altitude {target_m}m "
            f"(±{tolerance_m}m, timeout {timeout_s}s)..."
        )
        async def _wait():
            async for pos in self._drone.telemetry.position():
                if abs(pos.relative_altitude_m - target_m) <= tolerance_m:
                    logger.info(
                        f"Altitude reached: {pos.relative_altitude_m:.1f}m"
                    )
                    return True
            return False

        try:
            return await asyncio.wait_for(_wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            logger.warning(f"Altitude wait timed out after {timeout_s}s")
            return False
        except Exception as e:
            logger.warning(f"Altitude wait error: {e}")
            return False

    async def wait_for_landed(self, timeout_s: float = 60.0) -> bool:
        logger.info("Waiting for landing...")
        async def _wait():
            async for state in self._drone.telemetry.landed_state():
                if str(state) in ("ON_GROUND", "LandedState.ON_GROUND"):
                    logger.info("Vehicle has landed")
                    return True
            return False

        try:
            return await asyncio.wait_for(_wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            logger.warning(f"Landing wait timed out after {timeout_s}s")
            return False
        except Exception as e:
            logger.warning(f"Landing wait error: {e}")
            return False

    async def wait_for_disarmed(self, timeout_s: float = 60.0) -> bool:
        logger.info("Waiting for disarm...")
        async def _wait():
            async for armed in self._drone.telemetry.armed():
                if not armed:
                    logger.info("Vehicle is disarmed")
                    return True
            return False

        try:
            return await asyncio.wait_for(_wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            logger.warning(f"Disarm wait timed out after {timeout_s}s")
            return False
        except Exception as e:
            logger.warning(f"Disarm wait error: {e}")
            return False

    @property
    def is_offboard_active(self) -> bool:
        return self._offboard_active

    async def stop_offboard(self) -> None:
        if not self._offboard_active:
            return
        logger.info("Stopping offboard mode...")
        try:
            await self._drone.offboard.stop()
            self._offboard_active = False
            logger.info("Offboard mode stopped")
        except OffboardError as e:
            logger.error(f"Failed to stop offboard: {e._result.result}")
            self._offboard_active = False

    # ── Offboard commands (MAVSDK-specific, not in ABC) ──────

    async def start_offboard(self) -> None:
        """Enter offboard mode."""
        if self._offboard_active:
            logger.warning("Offboard already active")
            return
        logger.info("Starting offboard mode...")
        await self._drone.offboard.set_position_ned(
            PositionNedYaw(0.0, 0.0, 0.0, 0.0)
        )
        try:
            await self._drone.offboard.start()
            self._offboard_active = True
            logger.info("Offboard mode active")
        except OffboardError as e:
            logger.error(f"Failed to start offboard: {e._result.result}")
            raise

    async def send_velocity_ned(
        self, north_ms: float, east_ms: float,
        down_ms: float, yaw_deg: float = 0.0,
    ) -> None:
        """Send NED velocity setpoint."""
        await self._drone.offboard.set_velocity_ned(
            VelocityNedYaw(north_ms, east_ms, down_ms, yaw_deg)
        )

    async def send_velocity_body(
        self, forward_ms: float, right_ms: float,
        down_ms: float, yawspeed_degs: float = 0.0,
    ) -> None:
        """Send body-frame velocity setpoint."""
        await self._drone.offboard.set_velocity_body(
            VelocityBodyYawspeed(forward_ms, right_ms, down_ms, yawspeed_degs)
        )
