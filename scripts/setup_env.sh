#!/bin/bash
# ============================================================
# Drone Inspector — Environment Setup Script
# ============================================================
# One-click install for PX4 SITL + Gazebo + Python deps
# Tested on: Ubuntu 22.04 LTS
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PX4_DIR="$HOME/PX4-Autopilot"

echo "=============================================="
echo " Drone Inspector — Environment Setup"
echo "=============================================="
echo ""

# --- System dependencies ---
echo "[1/5] Installing system dependencies..."
sudo apt update
sudo apt install -y \
    git cmake build-essential \
    python3 python3-pip \
    curl wget unzip \
    libopencv-dev

# --- PX4 Autopilot ---
echo "[2/5] Setting up PX4 Autopilot..."
if [ ! -d "$PX4_DIR" ]; then
    echo "  Cloning PX4-Autopilot repository..."
    git clone https://github.com/PX4/PX4-Autopilot.git --recursive "$PX4_DIR"
else
    echo "  PX4-Autopilot already exists at $PX4_DIR, updating..."
    cd "$PX4_DIR" && git pull && git submodule update --init --recursive
fi

echo "  Running PX4 ubuntu setup script (installs Gazebo + toolchain)..."
cd "$PX4_DIR"
bash ./Tools/setup/ubuntu.sh --no-nuttx

# --- Python dependencies (installed into active Conda env) ---
echo "[3/5] Installing Python dependencies..."
cd "$PROJECT_DIR"
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# --- Node.js (for dashboard frontend) ---
echo "[4/5] Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo "  Installing Node.js 20 LTS..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
else
    echo "  Node.js already installed: $(node --version)"
fi

# --- Create data directories ---
echo "[5/5] Creating project directories..."
mkdir -p "$PROJECT_DIR/data/logs"
mkdir -p "$PROJECT_DIR/data/detections"
mkdir -p "$PROJECT_DIR/data/reports"

echo ""
echo "=============================================="
echo " Setup complete!"
echo "=============================================="
echo ""
echo " PX4-Autopilot:  $PX4_DIR"
echo " Python env:     Miniconda (active environment)"
echo ""
echo " Quick test PX4 SITL:"
echo "   cd $PX4_DIR && make px4_sitl gz_x500"
echo ""
echo " Or use the launch script:"
echo "   ./scripts/launch_sitl.sh"
echo ""
echo " NOTE: You may need to REBOOT after first run"
echo "       (for user group changes to take effect)"
echo "=============================================="
