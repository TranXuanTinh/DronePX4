# Architecture — Drone Inspector MVP

## System Overview

The Drone Inspector is a simulation-only autonomous inspection drone system built on **PX4 SITL**, **Gazebo Harmonic**, and **ROS 2 Jazzy**. It demonstrates end-to-end autonomous mission execution with computer vision, from takeoff through waypoint navigation, object detection, and return-to-launch.

The codebase is structured around **SOLID principles**, **OOP best practices**, and **GoF design patterns** to maximize testability, extensibility, and maintainability.

---

## Design Principles Applied

### SOLID Principles

| Principle | Implementation |
|-----------|---------------|
| **SRP** | Each module has one responsibility. State machine owns transitions; `MissionExecutor` owns behavior. Dashboard `main.py` is a thin shell; endpoints live in `routers/`. |
| **OCP** | Search patterns use Strategy pattern — new patterns require only a new class. Safety rules use Chain of Responsibility — new rules are added without editing existing code. |
| **LSP** | Camera implementations (`GstreamerCamera`, `VideoFileCamera`, `TestPatternCamera`) are all substitutable through the `CameraSource` ABC. |
| **ISP** | Interfaces are focused: `ObjectDetector` has only `load()` and `detect()`. `SafetyRule` has only `evaluate()`. No consumer is forced to depend on methods it doesn't use. |
| **DIP** | All consumers depend on abstract interfaces (`DroneConnector`, `FlightController`, `CameraSource`, etc.), never on concrete classes. |

### Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Strategy** | `SearchPatternStrategy` → `LawnmowerPattern`, `ExpandingSquarePattern`, `CustomWaypointsPattern` | Pluggable search patterns without if/elif chains |
| **Observer** | `EventBus` with `TelemetryEvent`, `DetectionFoundEvent`, `StateChangeEvent` | Decoupled pub/sub for telemetry, detections, and state changes |
| **Chain of Responsibility** | `SafetyRule` → `BatteryRule`, `GeofenceRule`, `AltitudeRule`, `ConnectionRule` | Composable safety checks; new rules added by appending |
| **Factory** | `CameraFactory`, `AppFactory`, `SafetyMonitor.from_config()` | Config-driven object construction |
| **State Machine** | `MissionStateMachine` (via `transitions` library) | Declarative state/transition management |
| **Template Method** | `MissionExecutor.do_xxx()` handlers | Consistent state handler contract |
| **Registry** | `PatternRegistry` | Auto-discovery of search pattern strategies |

---

## Module Dependency Graph

```mermaid
graph TB
    subgraph "Core Layer"
        types["core/types.py<br/>DTOs & Enums"]
        interfaces["core/interfaces.py<br/>ABCs"]
        geo["core/geo.py<br/>GPS Math"]
        events["core/events.py<br/>EventBus"]
    end

    subgraph "Bridge Layer"
        bridge["bridge/mavlink_bridge.py<br/>MAVLinkBridge"]
        commands["bridge/commands.py<br/>FlightCommands"]
        telemetry["bridge/telemetry.py<br/>TelemetryCollector"]
    end

    subgraph "Perception Layer"
        camera["perception/camera.py<br/>CameraFactory + 3 impls"]
        detector["perception/detector.py<br/>YOLODetector"]
        tracker["perception/tracker.py<br/>ByteTrackWrapper"]
        geotag["perception/geotagging.py<br/>GPSGeotagger"]
    end

    subgraph "Mission Layer"
        safety["mission/safety.py<br/>SafetyMonitor + Rules"]
        planner["mission/waypoint_planner.py<br/>PatternRegistry"]
        executor["mission/executor.py<br/>MissionExecutor"]
        sm["mission/state_machine.py<br/>MissionStateMachine"]
    end

    subgraph "Dashboard"
        app["dashboard/main.py<br/>FastAPI App"]
        deps["dashboard/dependencies.py<br/>AppContainer"]
        routers["dashboard/routers/<br/>5 router modules"]
    end

    subgraph "Streaming"
        overlay["streaming/overlay.py"]
        video["streaming/video_server.py"]
    end

    factory["factory.py<br/>AppFactory"]

    %% Core dependencies
    bridge --> interfaces
    bridge --> types
    commands --> interfaces
    commands --> bridge
    telemetry --> interfaces
    telemetry --> events

    camera --> interfaces
    detector --> interfaces
    detector --> types
    tracker --> interfaces
    tracker --> types
    geotag --> interfaces
    geotag --> geo

    safety --> interfaces
    safety --> geo
    planner --> interfaces
    planner --> geo
    executor --> interfaces
    executor --> geo
    sm --> executor

    video --> interfaces
    video --> types
    overlay --> types

    app --> factory
    app --> routers
    routers --> deps
    factory --> bridge
    factory --> commands
    factory --> camera
    factory --> detector
    factory --> tracker
    factory --> geotag
    factory --> safety
    factory --> sm
```

---

## Class Hierarchy (UML)

```mermaid
classDiagram
    class DroneConnector {
        <<interface>>
        +connect()
        +disconnect()
        +wait_for_ready()
        +is_connected: bool
        +latest_telemetry: TelemetryFrame
        +start_telemetry_stream()
        +stop_telemetry_stream()
    }
    class MAVLinkBridge {
        +drone: System
        +__aenter__()
        +__aexit__()
    }
    DroneConnector <|-- MAVLinkBridge

    class FlightController {
        <<interface>>
        +arm()
        +disarm()
        +takeoff()
        +land()
        +rtl()
        +goto()
        +hold()
    }
    class FlightCommands {
        +start_offboard()
        +send_velocity_ned()
    }
    FlightController <|-- FlightCommands

    class CameraSource {
        <<interface>>
        +open(): bool
        +get_frame(): ndarray
        +release()
        +frame_count: int
    }
    class GstreamerCamera
    class VideoFileCamera
    class TestPatternCamera
    CameraSource <|-- GstreamerCamera
    CameraSource <|-- VideoFileCamera
    CameraSource <|-- TestPatternCamera

    class ObjectDetector {
        <<interface>>
        +load()
        +detect(frame): List~Detection~
        +avg_inference_ms: float
    }
    class YOLODetector
    ObjectDetector <|-- YOLODetector

    class ObjectTracker {
        <<interface>>
        +update(detections): List~Track~
        +reset()
    }
    class ByteTrackWrapper
    ObjectTracker <|-- ByteTrackWrapper

    class SearchPatternStrategy {
        <<interface>>
        +name: str
        +generate(config): List~Waypoint~
    }
    class LawnmowerPattern
    class ExpandingSquarePattern
    class CustomWaypointsPattern
    SearchPatternStrategy <|-- LawnmowerPattern
    SearchPatternStrategy <|-- ExpandingSquarePattern
    SearchPatternStrategy <|-- CustomWaypointsPattern

    class SafetyRule {
        <<interface>>
        +name: str
        +evaluate(telemetry): SafetyAction
    }
    class BatteryRule
    class GeofenceRule
    class AltitudeRule
    class ConnectionRule
    SafetyRule <|-- BatteryRule
    SafetyRule <|-- GeofenceRule
    SafetyRule <|-- AltitudeRule
    SafetyRule <|-- ConnectionRule

    class SafetyChecker {
        <<interface>>
        +check(telemetry): SafetyAction
        +add_rule(rule)
    }
    class SafetyMonitor {
        +from_config(): SafetyMonitor
    }
    SafetyChecker <|-- SafetyMonitor
    SafetyMonitor o-- SafetyRule
```

---

## Mission State Machine

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> PREFLIGHT : start_mission
    PREFLIGHT --> TAKEOFF : checks_pass
    PREFLIGHT --> IDLE : checks_fail
    TAKEOFF --> SEARCH : altitude_reached
    SEARCH --> DETECT : object_detected
    SEARCH --> RTL : search_complete
    DETECT --> INSPECT : detection_confirmed
    DETECT --> SEARCH : false_positive
    INSPECT --> LOG : inspection_done
    LOG --> SEARCH : more_waypoints
    LOG --> RTL : mission_complete
    RTL --> LANDED : touchdown
    LANDED --> IDLE : disarmed

    PREFLIGHT --> ABORT : abort
    TAKEOFF --> ABORT : abort
    SEARCH --> ABORT : abort
    DETECT --> ABORT : abort
    INSPECT --> ABORT : abort
    LOG --> ABORT : abort
    ABORT --> RTL : abort_rtl

    TAKEOFF --> RTL : safety_rtl
    SEARCH --> RTL : safety_rtl
    DETECT --> RTL : safety_rtl
    INSPECT --> RTL : safety_rtl
    LOG --> RTL : safety_rtl
```

---

## Perception Pipeline

```mermaid
sequenceDiagram
    participant Camera as CameraSource
    participant Det as YOLODetector
    participant Track as ByteTrackWrapper
    participant Geo as GPSGeotagger
    participant SM as StateMachine
    participant Bus as EventBus

    loop Every frame (SEARCH state)
        SM->>Camera: get_frame()
        Camera-->>SM: BGR frame
        SM->>Det: detect(frame)
        Det-->>SM: List[Detection]
        SM->>Track: update(detections)
        Track-->>SM: List[Track]
        alt Confirmed tracks found
            SM->>Geo: tag_detections(tracks, gps, heading)
            Geo-->>SM: List[GeotaggedDetection]
            SM->>SM: object_detected → DETECT
            SM->>Bus: publish(DetectionFoundEvent)
        end
    end
```

---

## Dashboard Architecture

```mermaid
graph LR
    subgraph "Frontend (React + Vite)"
        UI["App.jsx"]
        SB["StatusBar"]
        VF["VideoFeed"]
        DM["DroneMap"]
        DL["DetectionLog"]
        TP["TelemetryPanel"]
        MC["MissionControl"]
    end

    subgraph "Backend (FastAPI)"
        R1["routers/mission.py"]
        R2["routers/telemetry.py"]
        R3["routers/detections.py"]
        R4["routers/video.py"]
        R5["routers/reports.py"]
        DC["dependencies.py<br/>AppContainer"]
    end

    UI --> SB
    UI --> VF
    UI --> DM
    UI --> DL
    UI --> TP
    UI --> MC

    MC -- "POST /api/mission/*" --> R1
    TP -- "WS /ws/telemetry" --> R2
    DL -- "WS /ws/detections" --> R3
    VF -- "WS /ws/video" --> R4
    MC -- "GET /api/report/*" --> R5

    R1 --> DC
    R2 --> DC
    R3 --> DC
    R4 --> DC
    R5 --> DC
```

---

## Directory Structure

```
DronePX4/
├── src/
│   ├── core/                    # Foundation layer
│   │   ├── types.py             #   DTOs: Position, TelemetryFrame, Detection, etc.
│   │   ├── interfaces.py        #   ABCs: DroneConnector, FlightController, etc.
│   │   ├── geo.py               #   GPS math: haversine, offset_gps
│   │   └── events.py            #   EventBus (Observer pattern)
│   ├── bridge/                  # PX4 communication
│   │   ├── mavlink_bridge.py    #   DroneConnector impl (MAVSDK)
│   │   ├── commands.py          #   FlightController impl
│   │   └── telemetry.py         #   TelemetryCollector
│   ├── perception/              # Computer vision
│   │   ├── camera.py            #   CameraSource impls + CameraFactory
│   │   ├── detector.py          #   ObjectDetector impl (YOLOv8)
│   │   ├── tracker.py           #   ObjectTracker impl (ByteTrack)
│   │   └── geotagging.py        #   Geotagger impl
│   ├── mission/                 # Autonomy
│   │   ├── state_machine.py     #   MissionStateMachine (transitions)
│   │   ├── executor.py          #   MissionExecutor (state handlers)
│   │   ├── safety.py            #   SafetyMonitor + Rules (CoR)
│   │   └── waypoint_planner.py  #   PatternRegistry + Strategies
│   ├── streaming/               # Video output
│   │   ├── video_server.py      #   WebSocket MJPEG server
│   │   └── overlay.py           #   Detection overlay renderer
│   ├── dashboard/               # Operator UI
│   │   ├── backend/
│   │   │   ├── main.py          #   FastAPI app (slim)
│   │   │   ├── dependencies.py  #   AppContainer (typed DI)
│   │   │   ├── routers/         #   5 endpoint modules
│   │   │   ├── models/          #   Pydantic schemas
│   │   │   └── api/             #   Report generators
│   │   └── frontend/            #   React + Vite
│   ├── factory.py               # AppFactory (central wiring)
│   └── utils/                   # Config & logging
├── tests/unit/                  # 66 unit tests
├── config/                      # YAML config, Gazebo worlds
├── docs/                        # Documentation
├── scripts/                     # Launch & test scripts
└── docker/                      # Docker compose
```

---

## Key Data Flow

1. **Telemetry**: PX4 SITL → MAVSDK → `MAVLinkBridge` → `TelemetryCollector` → `EventBus` → Dashboard WS
2. **Perception**: `CameraSource` → `YOLODetector` → `ByteTrackWrapper` → `GPSGeotagger` → `MissionExecutor`
3. **Commands**: Dashboard → `FlightController` → MAVSDK → PX4 SITL
4. **Safety**: `TelemetryFrame` → `SafetyMonitor` → `[BatteryRule, GeofenceRule, ...]` → `max(actions)` → State Machine

---

## Extending the System

### Add a New Search Pattern
```python
# 1. Create a new strategy class
class SpiralPattern(SearchPatternStrategy):
    @property
    def name(self) -> str: return "spiral"
    def generate(self, config: dict) -> List[Waypoint]: ...

# 2. Register it
PatternRegistry.register(SpiralPattern())
# Done — no existing code changes needed (OCP)
```

### Add a New Safety Rule
```python
# 1. Create a new rule
class WindSpeedRule(SafetyRule):
    @property
    def name(self) -> str: return "wind_speed"
    def evaluate(self, telemetry: TelemetryFrame) -> SafetyAction: ...

# 2. Add to monitor
monitor.add_rule(WindSpeedRule(max_wind_ms=15))
# Done — no existing code changes needed (OCP)
```

### Swap Detector Backend
```python
# Implement the ObjectDetector interface
class TensorRTDetector(ObjectDetector):
    def load(self) -> None: ...
    def detect(self, frame: np.ndarray) -> List[Detection]: ...
    @property
    def avg_inference_ms(self) -> float: ...

# Pass to state machine — no other code changes (DIP)
sm = MissionStateMachine(detector=TensorRTDetector(), ...)
```
