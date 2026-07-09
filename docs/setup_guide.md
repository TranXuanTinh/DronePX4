# Setup Guide

Complete setup instructions for running the Drone Inspector simulation.

## Prerequisites

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| **Ubuntu** | 22.04 LTS | `lsb_release -a` |
| **Python** | ≥ 3.10 | `python3 --version` |
| **Git** | any | `git --version` |
| **cmake** | ≥ 3.16 | `cmake --version` |
| **Node.js** | ≥ 18 (for dashboard) | `node --version` |

**Optional:**
- GPU with CUDA for faster YOLOv8 inference (CPU works fine for simulation)
- QGroundControl for visual telemetry monitoring

---

## Method A: Automated Setup (Recommended)

```bash
# Clone the repository
git clone <repo-url> DronePX4
cd DronePX4

# Run the setup script (installs everything)
chmod +x scripts/setup_env.sh
./scripts/setup_env.sh
```

The setup script installs:
1. System build dependencies (`cmake`, `build-essential`, etc.)
2. PX4-Autopilot source (cloned to `~/PX4-Autopilot`)
3. Gazebo Harmonic simulator (via PX4's `ubuntu.sh`)
4. Python virtual environment with all pip dependencies
5. Node.js 20 LTS (for the dashboard)
6. Project data directories

> **Note**: The first run may take **15-30 minutes** depending on your internet speed. PX4 compilation takes time.

After setup:
```bash
# You may need to reboot for user group changes
sudo reboot

# Activate the virtual environment
source .venv/bin/activate
```

---

## Method B: Docker Setup

```bash
cd docker

# Build and start all services
docker compose up --build

# Or in detached mode
docker compose up -d --build
```

Services:
- **px4-sitl**: PX4 SITL + Gazebo (ports 14540, 14550)
- **dashboard-backend**: FastAPI (port 8000)
- **dashboard-frontend**: React (port 3000)

---

## Method C: Manual Setup

### 1. Install PX4 Autopilot

```bash
# Clone PX4
git clone https://github.com/PX4/PX4-Autopilot.git --recursive ~/PX4-Autopilot

# Install dependencies (includes Gazebo)
cd ~/PX4-Autopilot
bash ./Tools/setup/ubuntu.sh --no-nuttx

# Build SITL (first build takes ~10 min)
make px4_sitl gz_x500
# Ctrl+C once it's running to verify the build works
```

### 2. Install Python Dependencies

```bash
cd /path/to/DronePX4

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Install Node.js (for dashboard)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install frontend dependencies
cd src/dashboard/frontend
npm install
```

---

## Verify Installation

### 1. Test PX4 SITL Launches

```bash
# Terminal 1: Launch SITL
./scripts/launch_sitl.sh

# You should see Gazebo open with a quadcopter
# PX4 console should print "Ready for takeoff!"
# Press Ctrl+C to stop
```

### 2. Run Unit Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

### 3. Test Mission (Headless)

```bash
# Terminal 1: Launch SITL
./scripts/launch_sitl.sh

# Terminal 2: Run mission
source .venv/bin/activate
python scripts/run_mission.py
```

### 4. Test Dashboard

```bash
# Terminal 1: PX4 SITL
./scripts/launch_sitl.sh

# Terminal 2: Backend
source .venv/bin/activate
cd src/dashboard/backend
uvicorn main:app --reload --port 8000

# Terminal 3: Frontend
cd src/dashboard/frontend
npm run dev

# Open http://localhost:3000
```

---

## Common Issues

### PX4 build fails with "Ninja not found"

```bash
sudo apt install ninja-build
```

### Gazebo doesn't open (headless server)

```bash
# Run in headless mode
./scripts/launch_sitl.sh --headless
```

### Python import errors

```bash
# Make sure venv is activated
source .venv/bin/activate

# Make sure you're in the project root
cd /path/to/DronePX4
```

### MAVSDK connection timeout

Ensure PX4 SITL is running before starting the mission script. The SITL process needs 10-15 seconds to initialize GPS simulation.

### Port 14540 already in use

```bash
# Kill any existing PX4 processes
pkill -f px4
pkill -f gz
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PX4_HOME` | `~/PX4-Autopilot` | PX4 source directory |
| `HEADLESS` | `0` | Set to `1` for no-GUI mode |
| `PX4_GZ_WORLD` | (default) | Custom Gazebo world name |
| `GZ_SIM_RESOURCE_PATH` | (auto) | Gazebo model search path |
