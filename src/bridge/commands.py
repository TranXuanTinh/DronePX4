"""
Flight Commands — High-level command wrappers for PX4 SITL.

Provides simple async methods for common flight operations:
arm, takeoff, land, goto, RTL, offboard mode management.
"""

import asyncio
import logging
from typing import Optional

from mavsdk.action import ActionError
from mavsdk.offboard import (
    OffboardError,
    PositionNedYaw,
    VelocityNedYaw,
    VelocityBodyYawspeed,
)

from src.bridge.mavlink_bridge import MAVLinkBridge

logger = logging.getLogger(__name__)


class FlightCommands:
    """High-level flight command wrappers around MAVSDK.

    Usage:
        bridge = MAVLinkBridge()
        await bridge.connect()
        cmd = FlightCommands(bridge)
        await cmd.arm()
        await cmd.takeoff(15.0)
    """

    def __init__(self, bridge: MAVLinkBridge):
        self._bridge = bridge
        self._drone = bridge.drone
        self._offboard_active = False
        self._setpoint_task: Optional[asyncio.Task] = None

    # === Basic Flight Commands ===

    async def arm(self) -> None:
        """Arm the vehicle."""
        logger.info("Arming vehicle...")
        try:
            await self._drone.action.arm()
            logger.info("Vehicle armed")
        except ActionError as e:
            logger.error(f"Arm failed: {e}")
            raise

    async def disarm(self) -> None:
        """Disarm the vehicle (only works on ground)."""
        logger.info("Disarming vehicle...")
        try:
            await self._drone.action.disarm()
            logger.info("Vehicle disarmed")
        except ActionError as e:
            logger.error(f"Disarm failed: {e}")
            raise

    async def takeoff(self, altitude_m: float = 15.0) -> None:
        """Command takeoff to specified altitude.

        Args:
            altitude_m: Target altitude in meters above takeoff point.
        """
        logger.info(f"Taking off to {altitude_m}m...")
        await self._drone.action.set_takeoff_altitude(altitude_m)
        try:
            await self._drone.action.takeoff()
            logger.info(f"Takeoff command sent (target: {altitude_m}m)")
        except ActionError as e:
            logger.error(f"Takeoff failed: {e}")
            raise

    async def land(self) -> None:
        """Command landing at current position."""
        logger.info("Landing...")
        try:
            await self._drone.action.land()
            logger.info("Land command sent")
        except ActionError as e:
            logger.error(f"Land failed: {e}")
            raise

    async def rtl(self) -> None:
        """Return to Launch."""
        logger.info("Returning to launch...")
        try:
            await self._drone.action.return_to_launch()
            logger.info("RTL command sent")
        except ActionError as e:
            logger.error(f"RTL failed: {e}")
            raise

    async def hold(self) -> None:
        """Hold position (exit offboard if active)."""
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
        """Navigate to a GPS coordinate.

        Args:
            latitude_deg: Target latitude
            longitude_deg: Target longitude
            altitude_m: Target altitude (AMSL)
            yaw_deg: Target yaw (NaN = maintain current heading)
        """
        logger.info(
            f"Going to ({latitude_deg:.6f}, {longitude_deg:.6f}) at {altitude_m:.1f}m"
        )
        try:
            await self._drone.action.goto_location(
                latitude_deg, longitude_deg, altitude_m, yaw_deg
            )
        except ActionError as e:
            logger.error(f"Goto failed: {e}")
            raise

    # === Altitude Monitoring ===

    async def wait_for_altitude(
        self, target_m: float, tolerance_m: float = 1.0, timeout_s: float = 30.0
    ) -> bool:
        """Wait until vehicle reaches target altitude.

        Args:
            target_m: Target relative altitude in meters
            tolerance_m: Acceptable deviation from target
            timeout_s: Maximum wait time

        Returns:
            True if altitude reached, False if timeout
        """
        logger.info(
            f"Waiting for altitude {target_m}m (±{tolerance_m}m, timeout {timeout_s}s)..."
        )
        try:
            async for pos in asyncio.timeout(timeout_s).__aenter__() or \
                    self._drone.telemetry.position():
                async for pos in self._drone.telemetry.position():
                    if abs(pos.relative_altitude_m - target_m) <= tolerance_m:
                        logger.info(
                            f"Altitude reached: {pos.relative_altitude_m:.1f}m"
                        )
                        return True
        except (asyncio.TimeoutError, TimeoutError):
            logger.warning(f"Altitude wait timed out after {timeout_s}s")
            return False

    async def wait_for_landed(self, timeout_s: float = 60.0) -> bool:
        """Wait until vehicle has landed.

        Returns:
            True if landed, False if timeout
        """
        logger.info("Waiting for landing...")
        try:
            start = asyncio.get_event_loop().time()
            async for state in self._drone.telemetry.landed_state():
                if str(state) in ("ON_GROUND", "LandedState.ON_GROUND"):
                    logger.info("Vehicle has landed")
                    return True
                if asyncio.get_event_loop().time() - start > timeout_s:
                    break
        except asyncio.TimeoutError:
            pass
        logger.warning(f"Landing wait timed out after {timeout_s}s")
        return False

    # === Offboard Mode Management ===

    async def start_offboard(self) -> None:
        """Enter offboard mode.

        Sends an initial setpoint (hold current position), then switches
        to OFFBOARD flight mode. Starts a background task to send
        heartbeat setpoints at 20 Hz.
        """
        if self._offboard_active:
            logger.warning("Offboard already active")
            return

        logger.info("Starting offboard mode...")

        # Send initial setpoint (required before starting offboard)
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

    async def stop_offboard(self) -> None:
        """Exit offboard mode (vehicle enters Hold mode)."""
        if not self._offboard_active:
            return

        logger.info("Stopping offboard mode...")
        try:
            await self._drone.offboard.stop()
            self._offboard_active = False
            logger.info("Offboard mode stopped")
        except OffboardError as e:
            logger.error(f"Failed to stop offboard: {e._result.result}")
            # Force flag off regardless
            self._offboard_active = False

    async def send_position_ned(
        self, north_m: float, east_m: float, down_m: float, yaw_deg: float = 0.0
    ) -> None:
        """Send NED position setpoint (relative to home).

        Args:
            north_m: North position in meters
            east_m: East position in meters
            down_m: Down position in meters (negative = up)
            yaw_deg: Yaw angle in degrees (0 = North)
        """
        await self._drone.offboard.set_position_ned(
            PositionNedYaw(north_m, east_m, down_m, yaw_deg)
        )

    async def send_velocity_ned(
        self,
        north_ms: float,
        east_ms: float,
        down_ms: float,
        yaw_deg: float = 0.0,
    ) -> None:
        """Send NED velocity setpoint.

        Args:
            north_ms: North velocity in m/s
            east_ms: East velocity in m/s
            down_ms: Down velocity in m/s (positive = descend)
            yaw_deg: Target yaw in degrees
        """
        await self._drone.offboard.set_velocity_ned(
            VelocityNedYaw(north_ms, east_ms, down_ms, yaw_deg)
        )

    async def send_velocity_body(
        self,
        forward_ms: float,
        right_ms: float,
        down_ms: float,
        yawspeed_degs: float = 0.0,
    ) -> None:
        """Send body-frame velocity setpoint.

        Args:
            forward_ms: Forward velocity in m/s
            right_ms: Right velocity in m/s
            down_ms: Down velocity in m/s
            yawspeed_degs: Yaw rotation speed in deg/s
        """
        await self._drone.offboard.set_velocity_body(
            VelocityBodyYawspeed(forward_ms, right_ms, down_ms, yawspeed_degs)
        )

    @property
    def is_offboard_active(self) -> bool:
        return self._offboard_active
