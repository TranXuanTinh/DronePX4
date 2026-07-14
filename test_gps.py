import asyncio
import time
from mavsdk import System

async def run():
    drone = System()
    print("Connecting to udpin://0.0.0.0:14540...")
    await drone.connect(system_address="udpin://0.0.0.0:14540")
    
    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected to drone!")
            break

    print("Checking health (wait for global position)...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok:
            print("Global position is OK based on health check!")
            break

    # Now let's see how long it takes for gps_info to yield FixType >= FIX_3D
    print("Starting gps_info stream at 1.0Hz")
    await drone.telemetry.set_rate_gps_info(1.0)
    
    start_time = time.time()
    async for info in drone.telemetry.gps_info():
        elapsed = time.time() - start_time
        print(f"[{elapsed:.2f}s] GPS INFO: sats={info.num_satellites}, fix_type={info.fix_type} ({info.fix_type.value})")
        if info.fix_type.value >= 3:
            print(f"Got 3D fix after {elapsed:.2f} seconds!")
            break

asyncio.run(run())
