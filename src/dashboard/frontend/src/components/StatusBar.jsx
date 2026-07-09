import React from 'react';

function getBadgeClass(state) {
  const s = (state || '').toUpperCase();
  if (s === 'IDLE' || s === 'LANDED') return 'idle';
  if (s === 'SEARCH') return 'search';
  if (s === 'DETECT' || s === 'INSPECT') return 'detect';
  if (s === 'RTL') return 'rtl';
  if (s === 'ABORT') return 'abort';
  return 'active';
}

export default function StatusBar({ connected, telemetry, missionState }) {
  const t = telemetry || {};

  return (
    <div className="status-bar">
      <span className="logo">🛸 Drone Inspector</span>

      <div className="status-item">
        <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
        <span>{connected ? 'SITL Connected' : 'Disconnected'}</span>
      </div>

      <div className="status-item">
        Mode: <span className="status-value">{t.flight_mode || '—'}</span>
      </div>

      <div className="status-item">
        <span className={`mission-state-badge ${getBadgeClass(missionState)}`}>
          {missionState || 'IDLE'}
        </span>
      </div>

      <div className="status-item">
        Battery: <span className="status-value" style={{
          color: (t.battery_percent || 100) < 20 ? '#ef4444' :
                 (t.battery_percent || 100) < 40 ? '#eab308' : '#22c55e'
        }}>
          {t.battery_percent != null ? `${t.battery_percent.toFixed(0)}%` : '—'}
        </span>
      </div>

      <div className="status-item">
        GPS: <span className="status-value">{t.gps_satellites ?? '—'} sats</span>
      </div>

      <div className="status-item">
        {t.armed
          ? <span style={{ color: '#22c55e', fontWeight: 600 }}>● ARMED</span>
          : <span style={{ color: '#64748b' }}>○ Disarmed</span>
        }
      </div>
    </div>
  );
}
