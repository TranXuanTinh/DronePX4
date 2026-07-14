import asyncio
from mavsdk import System

async def run():
    drone = System()
    print("Connecting...")
    await drone.connect(system_address="udp://:14540")
    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected!")
            break
    print("Getting telemetry...")
    async for health in drone.telemetry.health():
        print(f"Health: {health}")
        if health.is_global_position_ok and health.is_home_position_ok:
            print("Drone is ready to fly!")
            break

asyncio.run(run())
