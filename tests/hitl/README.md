# HITL (Hardware-In-The-Loop) Testing Guide

> **Status**: Stub framework — requires physical autopilot hardware.

## Overview

HITL tests run PX4 firmware directly on a physical Pixhawk autopilot
while using simulated sensors. This bridges the gap between pure SITL
simulation and real-world flight testing.

## Hardware Requirements

| Component | Specification |
|-----------|--------------|
| **Autopilot** | Pixhawk 6C, 6X, or Cube Orange |
| **Connection** | USB (for bench testing) or UART/telemetry radio |
| **Host PC** | Linux (Ubuntu 22.04+) with USB 3.0 |
| **Power** | USB bus power or bench power supply (5V, 3A) |

## PX4 HITL Configuration

1. Flash PX4 firmware to Pixhawk:
   ```bash
   make px4_fmu-v6c_default upload
   ```

2. Enable HITL mode in QGroundControl:
   - Vehicle Setup → Safety → HITL → Enable
   - Set `SYS_HITL = 1` parameter

3. Configure serial connection:
   ```bash
   export PX4_HITL_PORT="/dev/ttyACM0"
   export PX4_HITL_BAUD="921600"
   ```

## Running HITL Tests

```bash
# Run HITL tests (requires connected hardware)
python -m pytest tests/hitl/ -v --timeout=120

# With specific serial port
PX4_HITL_PORT=/dev/ttyUSB0 python -m pytest tests/hitl/ -v
```

## Safety Precautions

> ⚠️ **CRITICAL**: HITL tests send REAL commands to REAL hardware.

1. **Remove propellers** before bench testing
2. **Secure the vehicle** to the test bench
3. **Have a kill switch** ready (cut power to ESCs)
4. **Monitor battery voltage** — do not exceed safe discharge rates
5. **Test in a controlled environment** — no bystanders in the test area

## Sensor Injection

HITL mode uses simulated sensors injected via MAVLink:
- GPS: Simulated from Gazebo physics
- IMU: Computed from simulation dynamics
- Barometer: Derived from simulated altitude
- Magnetometer: Simulated from world model

The physical sensors on the Pixhawk are disabled in HITL mode.
