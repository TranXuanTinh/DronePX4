# 🛸 Drone Inspector — Autonomous Inspection Drone MVP

> **Simulation-Only** — PX4 SITL + Gazebo | No hardware required

An autonomous inspection drone system built on PX4 SITL with computer vision
(YOLOv8 + ByteTrack), an event-driven mission state machine, and a real-time
operator dashboard. Everything runs in simulation.

## 🏗️ Architecture

```
PX4 SITL ←→ MAVSDK-Python ←→ Mission State Machine
                                    ↓
Gazebo Camera → YOLOv8 → ByteTrack → GPS Geotagging
                                    ↓
                           Operator Dashboard
                     (React + FastAPI + WebSocket)
```

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Install PX4 SITL, Gazebo, Python deps, Node.js
chmod +x scripts/setup_env.sh
./scripts/setup_env.sh

# Activate virtual environment
source .venv/bin/activate
```

### 2. Launch PX4 SITL

```bash
# Terminal 1: Start PX4 SITL + Gazebo
./scripts/launch_sitl.sh
```

### 3. Run Mission

```bash
# Terminal 2: Execute autonomous mission
python scripts/run_mission.py

# With custom config:
python scripts/run_mission.py --config config/vehicle/sim_config.yaml
```

### 4. Launch Dashboard (optional)

```bash
# Terminal 3: Start backend
cd src/dashboard/backend && uvicorn main:app --reload --port 8000

# Terminal 4: Start frontend
cd src/dashboard/frontend && npm run dev
```

## 📋 Mission Flow

```
IDLE → PREFLIGHT → TAKEOFF → SEARCH → DETECT → INSPECT → LOG → RTL → LANDED
                                ↑                           |
                                └───── more waypoints ──────┘
```

- **SEARCH**: Lawnmower pattern with continuous object detection
- **DETECT**: Confirm detection over 5 consecutive frames
- **INSPECT**: Hover/orbit target, capture images
- **LOG**: Geotag and save detection record
- **Safety**: Battery, geofence, altitude monitoring → auto-RTL

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Flight Controller | PX4 v1.15+ (SITL) |
| Simulator | Gazebo Harmonic |
| Flight Control | MAVSDK-Python |
| Object Detection | YOLOv8 (Ultralytics) |
| Object Tracking | ByteTrack (custom impl) |
| Video Streaming | OpenCV + WebSocket MJPEG |
| Dashboard Backend | FastAPI + WebSocket |
| Dashboard Frontend | React + Vite + Leaflet |
| Reports | ReportLab (PDF) + CSV |

## 📁 Project Structure

```
DronePX4/
├── config/          # PX4 params, Gazebo worlds, vehicle config
├── src/
│   ├── bridge/      # MAVSDK connection, telemetry, commands
│   ├── perception/  # YOLOv8 detector, ByteTrack tracker, geotagging
│   ├── mission/     # State machine, safety, waypoint planner
│   ├── streaming/   # Video server, detection overlays
│   ├── dashboard/   # FastAPI backend + React frontend
│   └── utils/       # Logging, config, geo utilities
├── tests/           # Unit + integration tests
├── scripts/         # Setup, launch, run scripts
└── docker/          # Container configuration
```

## ⚙️ Configuration

Edit `config/vehicle/sim_config.yaml` to customize:
- Detection classes and confidence thresholds
- Search area, altitude, and pattern
- Safety geofence and battery limits
- Dashboard ports and video quality

## 📄 License

MIT
