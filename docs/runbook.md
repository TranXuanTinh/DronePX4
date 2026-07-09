# Runbook — Operating the Drone Inspector Simulation

## Quick Reference

| Action | Command |
|--------|---------|
| Start SITL | `./scripts/launch_sitl.sh` |
| Start SITL (headless) | `./scripts/launch_sitl.sh --headless` |
| Run mission | `python scripts/run_mission.py` |
| Run mission (custom config) | `python scripts/run_mission.py -c path/to/config.yaml` |
| Start dashboard backend | `uvicorn src.dashboard.backend.main:app --port 8000` |
| Start dashboard frontend | `cd src/dashboard/frontend && npm run dev` |
| Run tests | `python -m pytest tests/ -v` |
| Docker (all services) | `cd docker && docker compose up` |

---

## Standard Operating Procedure

### 1. Pre-Mission Checklist

- [ ] PX4 SITL is running and shows "Ready for takeoff!"
- [ ] Gazebo world is loaded (or `--headless` mode for CI)
- [ ] Python venv is activated (`source .venv/bin/activate`)
- [ ] Configuration reviewed in `config/vehicle/sim_config.yaml`
- [ ] Data directories exist (`data/logs`, `data/detections`, `data/reports`)

### 2. Launch Sequence

```bash
# Terminal 1: Start simulator
./scripts/launch_sitl.sh

# Wait for "Ready for takeoff!" message (~15 seconds)

# Terminal 2: Run mission
source .venv/bin/activate
python scripts/run_mission.py

# (Optional) Terminal 3+4: Start dashboard
uvicorn src.dashboard.backend.main:app --port 8000
cd src/dashboard/frontend && npm run dev
# Open http://localhost:3000
```

### 3. During Mission

- **Monitor**: Watch the dashboard for telemetry, video, and detections
- **Abort**: Press `Ctrl+C` in the mission terminal, or click "Abort" in the dashboard
- **Abort** triggers: ABORT → RTL → LANDED → IDLE (graceful)
- **Safety**: Battery, geofence, and altitude monitors run automatically

### 4. Post-Mission

- Review detections in the dashboard Detection Log
- Download PDF report: `http://localhost:8000/api/report/pdf`
- Download CSV export: `http://localhost:8000/api/report/csv`
- Check logs in `data/logs/mission.log`

---

## Configuration Reference

### Search Patterns

| Pattern | Config Value | Best For |
|---------|-------------|----------|
| Lawnmower (boustrophedon) | `lawnmower` | Rectangular area systematic coverage |
| Expanding Square | `expanding_square` | Point-of-interest search outward |
| Custom Waypoints | `custom` | User-defined inspection route |

### Detection Tuning

```yaml
# config/vehicle/sim_config.yaml → perception section
perception:
  confidence_threshold: 0.45  # Higher = fewer false positives
  classes:                     # Add/remove COCO classes
    - "person"
    - "car"
  tracker:
    track_buffer: 30           # Frames before losing a track
    track_thresh: 0.5          # Min confidence to create new track
```

### Safety Limits

```yaml
safety:
  geofence_radius_m: 500      # Max distance from home
  max_altitude_m: 120          # Altitude ceiling
  min_battery_percent: 20      # Triggers RTL warning
  critical_battery_percent: 10  # Triggers emergency land
```

---

## Troubleshooting

### Mission won't start (stuck at PREFLIGHT)

**Cause**: PX4 SITL hasn't established a GPS fix yet.
**Fix**: Wait 10-15 seconds after SITL launches for GPS simulation to initialize.

### No detections during SEARCH

**Cause**: The Gazebo world may not contain detectable objects, or the camera feed isn't active.
**Fix**: The system uses a synthetic test-pattern camera as fallback. Check `config/vehicle/sim_config.yaml` camera settings.

### Dashboard shows "Disconnected"

**Cause**: Backend not running or PX4 SITL not running.
**Fix**: Ensure both the SITL and backend are running. Check ports 14540 (SITL) and 8000 (API).

### High CPU usage during mission

**Cause**: YOLOv8 running on CPU.
**Fix**: Set `perception.device: "cuda:0"` in config if a GPU is available, or reduce camera FPS.

---

## API Endpoints Quick Reference

### REST

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | System health and connection status |
| GET | `/api/mission/status` | Current mission progress |
| POST | `/api/mission/start` | Start a new mission |
| POST | `/api/mission/abort` | Abort current mission |
| POST | `/api/mission/rtl` | Command Return to Launch |
| GET | `/api/detections` | List all detections |
| GET | `/api/snapshot` | Single JPEG camera snapshot |
| GET | `/api/report/csv` | Download CSV report |
| GET | `/api/report/pdf` | Download PDF report |

### WebSocket

| Endpoint | Data | Rate |
|----------|------|------|
| `/ws/telemetry` | JSON telemetry frames | 10 Hz |
| `/ws/detections` | JSON detection events | On detection |
| `/ws/video` | Binary JPEG frames | 15 FPS |
