import React from 'react';

export default function TelemetryPanel({ telemetry }) {
  const t = telemetry || {};

  const batteryPct = t.battery_percent ?? 100;
  const batteryColor = batteryPct < 20 ? '#ef4444' : batteryPct < 40 ? '#eab308' : '#22c55e';

  return (
    <div className="telemetry-panel card">
      <div className="card-header">
        <span>📊 Telemetry</span>
      </div>
      <div className="card-body">
        <div className="telemetry-grid">
          {/* Altitude */}
          <div className="telem-gauge">
            <div className="telem-label">Altitude</div>
            <div className="telem-value">{(t.altitude_m || 0).toFixed(1)}</div>
            <div className="telem-unit">meters</div>
          </div>

          {/* Speed */}
          <div className="telem-gauge">
            <div className="telem-label">Speed</div>
            <div className="telem-value">{(t.groundspeed_ms || 0).toFixed(1)}</div>
            <div className="telem-unit">m/s</div>
          </div>

          {/* Heading */}
          <div className="telem-gauge">
            <div className="telem-label">Heading</div>
            <div className="telem-value" style={{ fontSize: '24px' }}>
              {(t.heading_deg || 0).toFixed(0)}°
              <span style={{ marginLeft: '6px', fontSize: '16px' }}>
                {getCompass(t.heading_deg || 0)}
              </span>
            </div>
            <div className="telem-unit">degrees</div>
          </div>

          {/* Battery */}
          <div className="telem-gauge">
            <div className="telem-label">Battery</div>
            <div className="telem-value" style={{
              background: `linear-gradient(135deg, ${batteryColor}, ${batteryColor}dd)`,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}>
              {batteryPct.toFixed(0)}%
            </div>
            <div className="telem-unit">
              {t.battery_voltage ? `${t.battery_voltage.toFixed(1)}V` : '—'}
            </div>
            <div className="battery-bar-container">
              <div
                className="battery-bar-fill"
                style={{
                  width: `${batteryPct}%`,
                  background: batteryColor,
                }}
              />
            </div>
          </div>

          {/* GPS */}
          <div className="telem-gauge">
            <div className="telem-label">GPS</div>
            <div className="telem-value" style={{ fontSize: '22px' }}>
              {t.gps_satellites ?? '—'}
            </div>
            <div className="telem-unit">satellites</div>
          </div>

          {/* Flight Mode */}
          <div className="telem-gauge">
            <div className="telem-label">Mode</div>
            <div className="telem-value" style={{ fontSize: '16px', textTransform: 'uppercase' }}>
              {t.flight_mode || '—'}
            </div>
            <div className="telem-unit">{t.armed ? '🟢 Armed' : '⚪ Disarmed'}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function getCompass(deg) {
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const idx = Math.round(deg / 45) % 8;
  return dirs[idx];
}
