"""
Flight Commands — MAVSDK implementation of FlightController.

Provides high-level async methods for common flight operations.
Depends on DroneConnector (ABC), not the concrete MAVLinkBridge.
"""
from __future__ import annotations

import asyncio
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

    def __init__(self, bridge: MAVLinkBridge) -> None:
        self._bridge = bridge
        self._drone = bridge.drone
        self._offboard_active = False

    # ── FlightController interface ───────────────────────────

    async def arm(self) -> None:
        logger.info("Arming vehicle...")
        try:
            await self._drone.action.arm()
            logger.info("Vehicle armed")
        except ActionError as e:
            logger.error(f"Arm failed: {e}")
            raise

    async def disarm(self) -> None:
        logger.info("Disarming vehicle...")
        try:
            await self._drone.action.disarm()
            logger.info("Vehicle disarmed")
        except ActionError as e:
            logger.error(f"Disarm failed: {e}")
            raise

    async def takeoff(self, altitude_m: float = 15.0) -> None:
        logger.info(f"Taking off to {altitude_m}m...")
        await self._drone.action.set_takeoff_altitude(altitude_m)
        try:
            await self._drone.action.takeoff()
            logger.info(f"Takeoff command sent (target: {altitude_m}m)")
        except ActionError as e:
            logger.error(f"Takeoff failed: {e}")
            raise

    async def land(self) -> None:
        logger.info("Landing...")
        try:
            await self._drone.action.land()
            logger.info("Land command sent")
        except ActionError as e:
            logger.error(f"Land failed: {e}")
            raise

    async def rtl(self) -> None:
        logger.info("Returning to launch...")
        try:
            await self._drone.action.return_to_launch()
            logger.info("RTL command sent")
        except ActionError as e:
            logger.error(f"RTL failed: {e}")
            raise

    async def hold(self) -> None:
        logger.info("Holding position...")
        if self._offboard_active:
            await self.stop_offboard()
        try:
            await self._drone.action.hold()
            logger.info("Hold command sent")
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
        try:
            await self._drone.action.goto_location(
                latitude_deg, longitude_deg, altitude_m, yaw_deg,
            )
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
        start = time.monotonic()
        try:
            async for pos in self._drone.telemetry.position():
                if abs(pos.relative_altitude_m - target_m) <= tolerance_m:
                    logger.info(
                        f"Altitude reached: {pos.relative_altitude_m:.1f}m"
                    )
                    return True
                if time.monotonic() - start > timeout_s:
                    break
        except asyncio.TimeoutError:
            pass
        logger.warning(f"Altitude wait timed out after {timeout_s}s")
        return False

    async def wait_for_landed(self, timeout_s: float = 60.0) -> bool:
        logger.info("Waiting for landing...")
        start = time.monotonic()
        try:
            async for state in self._drone.telemetry.landed_state():
                if str(state) in ("ON_GROUND", "LandedState.ON_GROUND"):
                    logger.info("Vehicle has landed")
                    return True
                if time.monotonic() - start > timeout_s:
                    break
        except asyncio.TimeoutError:
            pass
        logger.warning(f"Landing wait timed out after {timeout_s}s")
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
