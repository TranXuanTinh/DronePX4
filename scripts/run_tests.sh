#!/bin/bash
# ============================================================
# Drone Inspector — Test Runner
# ============================================================
# Runs unit tests with ROS pytest plugin conflicts resolved.
# Usage: ./scripts/run_tests.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=============================================="
echo " Running Drone Inspector Unit Tests"
echo "=============================================="
echo ""

# Deactivate ROS plugins that conflict with our test suite
export PYTHONDONTWRITEBYTECODE=1

python3 -c "
import sys, os, inspect, numpy as np
sys.path.insert(0, '.')

total_passed = 0
total_failed = 0

def run_tests(module_path, fixture_providers=None):
    global total_passed, total_failed
    import importlib.util
    spec = importlib.util.spec_from_file_location('test_module', module_path)
    mod = importlib.util.load_module(spec)
    spec.loader.exec_module(mod)

    for name, cls in inspect.getmembers(mod, inspect.isclass):
        if not name.startswith('Test'):
            continue
        obj = cls()
        for method_name in sorted(dir(obj)):
            if not method_name.startswith('test_'):
                continue
            method = getattr(obj, method_name)
            sig = inspect.signature(method)
            try:
                kwargs = {}
                for param in sig.parameters:
                    if fixture_providers and param in fixture_providers:
                        kwargs[param] = fixture_providers[param]()
                method(**kwargs)
                print(f'  ✅ {name}.{method_name}')
                total_passed += 1
            except Exception as e:
                print(f'  ❌ {name}.{method_name}: {e}')
                total_failed += 1

# Import and run each test module
from src.mission.waypoint_planner import WaypointPlanner
from src.mission.safety import SafetyMonitor
from src.perception.tracker import ByteTrackWrapper
from src.perception.geotagging import GPSGeotagger

print('📦 Waypoint Planner')
run_tests('tests/unit/test_waypoint_planner.py')
print()

print('📦 Tracker')
run_tests('tests/unit/test_tracker.py', {
    'tracker': lambda: ByteTrackWrapper(track_thresh=0.5, match_thresh=0.8, track_buffer=5, frame_rate=10),
})
print()

print('📦 Safety Monitor')
run_tests('tests/unit/test_safety.py', {
    'monitor': lambda: SafetyMonitor(geofence_radius_m=500, max_altitude_m=120, min_battery_pct=20, critical_battery_pct=10, home_lat=47.397742, home_lon=8.545594),
})
print()

print('📦 Geotagging')
run_tests('tests/unit/test_geotagging.py', {
    'geotagger': lambda: GPSGeotagger(camera_hfov_deg=60.0, image_width=640, image_height=480),
})
print()

print('==============================================')
print(f'  Results: {total_passed} passed, {total_failed} failed')
print('==============================================')

if total_failed > 0:
    sys.exit(1)
"

echo ""
echo "Done!"
