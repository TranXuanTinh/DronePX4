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
  const [statusMessage, setStatusMessage] = useState(null);

  // --- Status message auto-clear ---
  useEffect(() => {
    if (statusMessage) {
      const timer = setTimeout(() => setStatusMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [statusMessage]);

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
      setStatusMessage({ type: 'info', text: 'Starting mission...' });
      const res = await fetch(`${API_BASE}/api/mission/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pattern: 'lawnmower' }),
      });
      const data = await res.json();
      if (data.success) {
        setStatusMessage({ type: 'success', text: data.message });
      } else {
        setStatusMessage({ type: 'error', text: data.message || 'Start failed' });
      }
    } catch (e) {
      setStatusMessage({ type: 'error', text: `Start failed: ${e.message}` });
    }
  }, []);

  const abortMission = useCallback(async () => {
    if (!confirm('Abort mission and return to launch?')) return;
    try {
      const res = await fetch(`${API_BASE}/api/mission/abort`, { method: 'POST' });
      const data = await res.json();
      setStatusMessage({ type: 'warning', text: data.message || 'Abort commanded' });
    } catch (e) {
      setStatusMessage({ type: 'error', text: `Abort failed: ${e.message}` });
    }
  }, []);

  const commandRTL = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/mission/rtl`, { method: 'POST' });
      const data = await res.json();
      setStatusMessage({ type: 'info', text: data.message || 'RTL commanded' });
    } catch (e) {
      setStatusMessage({ type: 'error', text: `RTL failed: ${e.message}` });
    }
  }, []);

  const downloadCSV = useCallback(async () => {
    try {
      setStatusMessage({ type: 'info', text: 'Generating CSV report...' });
      const res = await fetch(`${API_BASE}/api/report/csv`);
      if (!res.ok) {
        const errText = await res.text();
        setStatusMessage({ type: 'error', text: `CSV export failed: ${errText}` });
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'detection_report.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setStatusMessage({ type: 'success', text: 'CSV report downloaded' });
    } catch (e) {
      setStatusMessage({ type: 'error', text: `CSV export failed: ${e.message}` });
    }
  }, []);

  const downloadPDF = useCallback(async () => {
    try {
      setStatusMessage({ type: 'info', text: 'Generating PDF report...' });
      const res = await fetch(`${API_BASE}/api/report/pdf`);
      if (!res.ok) {
        const errText = await res.text();
        setStatusMessage({ type: 'error', text: `PDF export failed: ${errText}` });
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'mission_report.pdf';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setStatusMessage({ type: 'success', text: 'PDF report downloaded' });
    } catch (e) {
      setStatusMessage({ type: 'error', text: `PDF export failed: ${e.message}` });
    }
  }, []);

  return (
    <div className="dashboard">
      <StatusBar
        connected={connected}
        telemetry={telemetry}
        missionState={missionState}
      />

      {/* Status Toast */}
      {statusMessage && (
        <div className={`status-toast status-toast-${statusMessage.type}`}>
          <span>{statusMessage.text}</span>
          <button
            className="status-toast-close"
            onClick={() => setStatusMessage(null)}
          >
            ✕
          </button>
        </div>
      )}

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
