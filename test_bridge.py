import asyncio
import logging
from src.bridge.mavlink_bridge import MAVLinkBridge

logging.basicConfig(level=logging.DEBUG)

async def run():
    bridge = MAVLinkBridge()
    try:
        print("Attempting to connect...")
        await bridge.connect()
        print("Connected!")
        print("Waiting for ready...")
        await bridge.wait_for_ready(timeout=60.0)
        print("Ready!")
    except Exception as e:
        print(f"Exception: {e}")
    finally:
        await bridge.disconnect()

asyncio.run(run())
