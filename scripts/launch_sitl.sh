#!/bin/bash
# ============================================================
# Drone Inspector — Launch PX4 SITL + Gazebo
# ============================================================
# Usage:
#   ./launch_sitl.sh              # Default: x500 quadcopter
#   ./launch_sitl.sh --world inspection_site
#   ./launch_sitl.sh --headless   # No GUI (CI/testing)
# ============================================================

set -e

PX4_DIR="${PX4_HOME:-$HOME/PX4-Autopilot}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Defaults
MODEL="gz_x500"
WORLD=""
HEADLESS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --model)
            MODEL="$2"
            shift 2
            ;;
        --world)
            WORLD="$2"
            shift 2
            ;;
        --headless)
            HEADLESS=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --model MODEL    Gazebo model (default: gz_x500)"
            echo "  --world WORLD    Custom Gazebo world name"
            echo "  --headless       Run without GUI"
            echo "  --help           Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check PX4 directory
if [ ! -d "$PX4_DIR" ]; then
    echo "ERROR: PX4-Autopilot not found at $PX4_DIR"
    echo "Run ./scripts/setup_env.sh first, or set PX4_HOME."
    exit 1
fi

# Add custom Gazebo models/worlds to search path
export GZ_SIM_RESOURCE_PATH="${PROJECT_DIR}/config/gazebo/models:${GZ_SIM_RESOURCE_PATH:-}"
export GZ_SIM_WORLD_PATH="${PROJECT_DIR}/config/gazebo/worlds:${GZ_SIM_WORLD_PATH:-}"

# Force discrete NVIDIA GPU utilization for Gazebo rendering on hybrid graphics systems
export __NV_PRIME_RENDER_OFFLOAD=1
export __GLX_VENDOR_LIBRARY_NAME=nvidia

# Headless mode
if [ "$HEADLESS" = true ]; then
    export HEADLESS=1
    echo "Running in headless mode (no GUI)"
fi

# Set custom world if specified
if [ -n "$WORLD" ]; then
    export PX4_GZ_WORLD="$WORLD"
    echo "Using custom world: $WORLD"
fi

echo "Cleaning up orphaned PX4/Gazebo processes..."
killall -q -9 gz ruby px4 mavsdk_server 2>/dev/null || true
sleep 1

echo "=============================================="
echo " Launching PX4 SITL"
echo "  Model:  $MODEL"
echo "  PX4:    $PX4_DIR"
if [ -n "$WORLD" ]; then
echo "  World:  $WORLD"
fi
echo "=============================================="
echo ""
echo " MAVLink ports:"
echo "   MAVSDK:  udp://:14540"
echo "   QGC:     udp://:14550"
echo ""
echo " Press Ctrl+C to stop"
echo "=============================================="
echo ""

# Apply PX4 parameter overrides for autonomous SITL operation
# (disables GCS/RC requirements — see config/px4_params/sitl_overrides.sh)
OVERRIDES="${PROJECT_DIR}/config/px4_params/sitl_overrides.sh"
if [ -f "$OVERRIDES" ]; then
    source "$OVERRIDES"
else
    echo "WARNING: SITL overrides not found at $OVERRIDES"
    echo "GCS connection may be required. Run without QGC at your own risk."
fi

cd "$PX4_DIR"
make px4_sitl "$MODEL"
