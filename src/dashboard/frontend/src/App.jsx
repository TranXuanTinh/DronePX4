import React, { useState, useEffect, useRef, useCallback } from 'react';
import StatusBar from './components/StatusBar.jsx';
import VideoFeed from './components/VideoFeed.jsx';
import DroneMap from './components/DroneMap.jsx';
import DetectionLog from './components/DetectionLog.jsx';
import TelemetryPanel from './components/TelemetryPanel.jsx';
import MissionControl from './components/MissionControl.jsx';

const WS_BASE = `ws://${window.location.hostname}:8000`;
const API_BASE = `http://${window.location.hostname}:8000`;

export default function App() {
  const [telemetry, setTelemetry] = useState(null);
  const [detections, setDetections] = useState([]);
  const [missionState, setMissionState] = useState('IDLE');
  const [connected, setConnected] = useState(false);
  const [flightPath, setFlightPath] = useState([]);

  // --- Telemetry WebSocket ---
  useEffect(() => {
    let ws;
    let reconnectTimer;

    function connect() {
      ws = new WebSocket(`${WS_BASE}/ws/telemetry`);

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        reconnectTimer = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setTelemetry(data);
        setMissionState(data.mission_state || 'IDLE');

        // Append to flight path (throttled)
        if (data.armed && data.latitude !== 0) {
          setFlightPath(prev => {
            const last = prev[prev.length - 1];
            if (!last || Math.abs(last[0] - data.latitude) > 0.000001 ||
                Math.abs(last[1] - data.longitude) > 0.000001) {
              return [...prev.slice(-500), [data.latitude, data.longitude]];
            }
            return prev;
          });
        }
      };
    }

    connect();
    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  // --- Detections WebSocket ---
  useEffect(() => {
    let ws;
    let reconnectTimer;

    function connect() {
      ws = new WebSocket(`${WS_BASE}/ws/detections`);
      ws.onclose = () => { reconnectTimer = setTimeout(connect, 3000); };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        const det = JSON.parse(event.data);
        setDetections(prev => [...prev, det]);
      };
    }

    connect();
    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  // --- Mission Commands ---
  const startMission = useCallback(async () => {
    try {
      setDetections([]);
      setFlightPath([]);
      const res = await fetch(`${API_BASE}/api/mission/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pattern: 'lawnmower' }),
      });
      const data = await res.json();
      if (!data.success) alert(data.message);
    } catch (e) {
      alert(`Start failed: ${e.message}`);
    }
  }, []);

  const abortMission = useCallback(async () => {
    if (!confirm('Abort mission and return to launch?')) return;
    try {
      await fetch(`${API_BASE}/api/mission/abort`, { method: 'POST' });
    } catch (e) {
      alert(`Abort failed: ${e.message}`);
    }
  }, []);

  const commandRTL = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/api/mission/rtl`, { method: 'POST' });
    } catch (e) {
      alert(`RTL failed: ${e.message}`);
    }
  }, []);

  const downloadCSV = useCallback(() => {
    window.open(`${API_BASE}/api/report/csv`, '_blank');
  }, []);

  const downloadPDF = useCallback(() => {
    window.open(`${API_BASE}/api/report/pdf`, '_blank');
  }, []);

  return (
    <div className="dashboard">
      <StatusBar
        connected={connected}
        telemetry={telemetry}
        missionState={missionState}
      />

      <VideoFeed wsUrl={`${WS_BASE}/ws/video`} />

      <DroneMap
        telemetry={telemetry}
        detections={detections}
        flightPath={flightPath}
      />

      <DetectionLog detections={detections} />

      <TelemetryPanel telemetry={telemetry} />

      <MissionControl
        missionState={missionState}
        onStart={startMission}
        onAbort={abortMission}
        onRTL={commandRTL}
        onDownloadCSV={downloadCSV}
        onDownloadPDF={downloadPDF}
      />
    </div>
  );
}
