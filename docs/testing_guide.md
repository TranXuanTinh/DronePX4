# Drone Inspector — Testing Guide

This guide covers the aviation-grade automation testing framework for the Drone Inspector project, aligned with DO-178C, DO-254, and ISO 21384 compliance.

## Testing Architecture

The framework is divided into five distinct layers to provide bi-directional traceability and isolate failures:

1. **Layer 1: Unit Tests** (`tests/unit/`)
   Tests individual components (e.g., `MissionExecutor`, `FlightCommands`) in isolation using mocks for external dependencies like `MAVSDK`.
2. **Layer 2: Integration Tests** (`tests/integration/`)
   Validates cross-component wiring and EventBus communication. Uses the real `AppFactory` but mocks external hardware.
3. **Layer 3: SITL End-to-End Tests** (`tests/sitl/`)
   Requires a live PX4 Gazebo simulation. Tests full mission lifecycles, real MAVLink communication, and waypoint navigation.
4. **Layer 4: Failsafe & Emergency Tests** (`tests/failsafe/`)
   Validates FAA/EASA compliance rules: Geofencing, Loss of Link (LOL), Low Battery, and Altitude Limits. Tests the `SafetyMonitor` triggering state machine aborts.
5. **Layer 5: Protocol Integrity Tests** (`tests/protocol/`)
   Validates telemetry data bounds, EventBus latency, and command retry mechanics (simulating degraded gRPC links).

## Running Tests

A unified test runner script is provided at `scripts/run_tests.sh`.

### Prerequisites
Make sure you are using the virtual environment with dependencies installed:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Commands

**Run all CI/CD (offline) tests:**
```bash
./scripts/run_tests.sh
```
*(This automatically skips SITL and HITL tests)*

**Run a specific test layer:**
```bash
./scripts/run_tests.sh --layer failsafe
./scripts/run_tests.sh --layer unit
```

**Run SITL tests (Requires PX4 simulator running):**
1. First, launch the simulator:
   ```bash
   ./scripts/launch_sitl.sh
   ```
2. Run the tests in another terminal:
   ```bash
   ./scripts/run_tests.sh --sitl
   ```

**Generate DO-178C Traceability Report:**
```bash
./scripts/run_tests.sh --traceability
```
This parses `tests/traceability/requirements_matrix.yaml` and reports on code coverage mapping.

## Traceability & Compliance

All test functions include a docstring mapping to a specific requirement, for example:
`"""REQ-BAT-002: Low battery (< 20%) triggers RTL_NOW."""`

The `tests/traceability/requirements_matrix.yaml` file maintains the mapping between:
1. The Requirement ID (e.g., `REQ-BAT-002`)
2. The Implementation Source File (`src/mission/safety.py`)
3. The Test Function (`test_low_battery_triggers_rtl`)

This structure provides the strict bi-directional traceability required by aviation software standards.
