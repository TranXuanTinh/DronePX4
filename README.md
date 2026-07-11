# 🛸 Drone Inspector — Autonomous Inspection Drone MVP

> **Simulation-Only** — PX4 SITL + Gazebo Harmonic + ROS 2 Jazzy | No hardware required

An autonomous inspection drone system built on PX4 SITL with computer vision
(YOLOv8 + ByteTrack), an event-driven mission state machine, and a real-time
operator dashboard. Everything runs in simulation.

---

## 🏗️ Architecture

```
PX4 SITL  ←→  MAVSDK-Python  ←→  Mission State Machine
                                        ↓
Gazebo Camera → YOLOv8 → ByteTrack → GPS Geotagging
                                        ↓
                               Operator Dashboard
                         (React + FastAPI + WebSocket)
```

The codebase is designed around **SOLID principles** and **GoF design patterns**:

| Pattern | Application |
|---------|-------------|
| **Strategy** | Pluggable search patterns (`LawnmowerPattern`, `ExpandingSquarePattern`, ...) |
| **Observer** | `EventBus` for decoupled telemetry/detection/state events |
| **Chain of Responsibility** | Composable safety rules (`BatteryRule`, `GeofenceRule`, ...) |
| **Factory** | `CameraFactory`, `AppFactory` for config-driven construction |
| **State Machine** | `MissionStateMachine` with declarative transitions |
| **Dependency Inversion** | All consumers depend on ABCs (`DroneConnector`, `FlightController`, `CameraSource`, ...) |

> 📄 Full architecture docs: [docs/architecture.md](docs/architecture.md)

---

## 🚀 Quick Start

### Prerequisites

- Ubuntu 22.04+ with ROS 2 Jazzy
- PX4 Autopilot v1.15+ (SITL)
- Gazebo Harmonic
- Python 3.10+
- Node.js 18+ (for dashboard frontend)

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

---

## 📋 Mission State Machine

```
IDLE → PREFLIGHT → TAKEOFF → SEARCH → DETECT → INSPECT → LOG → RTL → LANDED
                                ↑                           |
                                └───── more waypoints ──────┘
```

| State | Description |
|-------|-------------|
| **PREFLIGHT** | Check GPS fix, vehicle health, connection |
| **TAKEOFF** | Arm → takeoff to configured altitude |
| **SEARCH** | Navigate waypoints with continuous perception |
| **DETECT** | Confirm detection over consecutive frames |
| **INSPECT** | Hover over target, capture imagery |
| **LOG** | Geotag detection, decide resume/RTL |
| **RTL** | Return to launch position |
| **ABORT** | Safety-triggered → immediate RTL |

Safety monitoring runs continuously: battery, geofence, altitude, connection → auto-RTL.

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Flight Controller | PX4 v1.15+ (SITL) |
| Simulator | Gazebo Harmonic |
| ROS 2 | Jazzy Jalisco |
| Flight Control | MAVSDK-Python |
| Object Detection | YOLOv8 (Ultralytics) |
| Object Tracking | ByteTrack (custom impl) |
| Video Streaming | OpenCV + WebSocket MJPEG |
| Dashboard Backend | FastAPI + WebSocket |
| Dashboard Frontend | React + Vite + Leaflet |
| Reports | ReportLab (PDF) + CSV |
| Language | Python 3.10+ |

---

## 📁 Project Structure

```
DronePX4/
├── src/
│   ├── core/                        # ← Foundation layer (NEW)
│   │   ├── types.py                 #   DTOs: Position, TelemetryFrame, Detection, etc.
│   │   ├── interfaces.py            #   ABCs: DroneConnector, FlightController, etc.
│   │   ├── geo.py                   #   GPS math: haversine, offset_gps
│   │   └── events.py                #   EventBus (Observer pattern)
│   ├── bridge/                      # PX4 communication
│   │   ├── mavlink_bridge.py        #   DroneConnector impl (MAVSDK)
│   │   ├── commands.py              #   FlightController impl
│   │   └── telemetry.py             #   TelemetryCollector
│   ├── perception/                  # Computer vision
│   │   ├── camera.py                #   CameraSource impls + CameraFactory
│   │   ├── detector.py              #   ObjectDetector impl (YOLOv8)
│   │   ├── tracker.py               #   ObjectTracker impl (ByteTrack)
│   │   └── geotagging.py            #   Geotagger impl
│   ├── mission/                     # Autonomy
│   │   ├── state_machine.py         #   MissionStateMachine (transitions lib)
│   │   ├── executor.py              #   MissionExecutor (state handlers)
│   │   ├── safety.py                #   SafetyMonitor + Rules (Chain of Resp.)
│   │   └── waypoint_planner.py      #   PatternRegistry + Strategies
│   ├── streaming/                   # Video output
│   │   ├── video_server.py          #   WebSocket MJPEG server
│   │   └── overlay.py               #   Detection overlay renderer
│   ├── dashboard/                   # Operator UI
│   │   ├── backend/
│   │   │   ├── main.py              #   FastAPI app (slim entry point)
│   │   │   ├── dependencies.py      #   AppContainer (typed DI)
│   │   │   ├── routers/             #   mission, telemetry, detections, video, reports
│   │   │   ├── models/schemas.py    #   Pydantic schemas
│   │   │   └── api/reports.py       #   PDF report generator
│   │   └── frontend/                #   React + Vite
│   ├── factory.py                   # AppFactory (central wiring)
│   └── utils/                       # Config loader, logging
├── tests/
│   └── unit/                        # 66 unit tests
│       ├── test_core.py             #   EventBus, geo utilities
│       ├── test_waypoint_planner.py #   Strategy pattern + PatternRegistry
│       ├── test_tracker.py          #   ByteTrack ObjectTracker
│       ├── test_safety.py           #   Chain of Responsibility rules
│       └── test_geotagging.py       #   GPS projection
├── config/                          # YAML config, Gazebo worlds, PX4 params
├── docs/
│   └── architecture.md              # Full architecture + UML diagrams
├── scripts/                         # Launch, setup, test scripts
└── docker/                          # Docker compose
```

---

## 🔌 API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mission/start` | Start inspection mission |
| `POST` | `/api/mission/abort` | Abort → RTL |
| `POST` | `/api/mission/rtl` | Return to launch |
| `GET`  | `/api/mission/status` | Mission state, progress, battery |
| `GET`  | `/api/status` | System health (connection, GPS, uptime) |
| `GET`  | `/api/detections` | All geotagged detection events |
| `GET`  | `/api/snapshot` | Single JPEG frame |
| `GET`  | `/api/report/csv` | Download CSV detection report |
| `GET`  | `/api/report/pdf` | Download PDF mission report |

### WebSocket Endpoints

| Endpoint | Description | Data |
|----------|-------------|------|
| `/ws/telemetry` | Real-time telemetry @ 10 Hz | `TelemetryData` JSON |
| `/ws/detections` | Detection events as they occur | `DetectionEvent` JSON |
| `/ws/video` | MJPEG video with overlays | Binary JPEG frames |

---

## 🧩 Extending the System

### Add a New Search Pattern (Strategy)
```python
from src.core.interfaces import SearchPatternStrategy
from src.mission.waypoint_planner import PatternRegistry

class SpiralPattern(SearchPatternStrategy):
    @property
    def name(self) -> str: return "spiral"
    def generate(self, config: dict) -> list:
        # ... your waypoint generation logic ...
        pass

PatternRegistry.register(SpiralPattern())
```

### Add a New Safety Rule (Chain of Responsibility)
```python
from src.core.interfaces import SafetyRule

class WindSpeedRule(SafetyRule):
    @property
    def name(self) -> str: return "wind_speed"
    def evaluate(self, telemetry) -> SafetyAction:
        # ... your safety logic ...
        pass

monitor.add_rule(WindSpeedRule())
```

### Swap the Detector Backend (Dependency Inversion)
```python
from src.core.interfaces import ObjectDetector

class TensorRTDetector(ObjectDetector):
    def load(self) -> None: ...
    def detect(self, frame) -> list: ...
    @property
    def avg_inference_ms(self) -> float: ...

# Just pass it in — no other code changes needed
sm = MissionStateMachine(detector=TensorRTDetector(), ...)
```

---

## ⚙️ Configuration

Edit `config/vehicle/sim_config.yaml` to customize:

| Section | Parameters |
|---------|-----------|
| `connection` | MAVSDK address (`udp://:14540`) |
| `camera` | Source type, resolution, FPS, HFOV |
| `perception` | Model path, device, confidence threshold, target classes |
| `mission` | Search pattern, area, altitude, spacing |
| `safety` | Geofence radius, max altitude, battery thresholds |
| `dashboard` | Telemetry rate, video quality, port |

---

## 🧪 Testing

```bash
# Run all unit tests (66 tests)
python -m pytest tests/unit/ -v

# Run specific test module
python -m pytest tests/unit/test_safety.py -v

# Run with coverage
python -m pytest tests/unit/ --cov=src --cov-report=term-missing
```

---

## 📄 License

MIT
