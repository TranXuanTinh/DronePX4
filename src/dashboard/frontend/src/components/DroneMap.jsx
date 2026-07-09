import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';

// Custom drone icon
const droneIcon = L.divIcon({
  html: '<div style="font-size:24px;text-align:center;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.5))">🛸</div>',
  className: '',
  iconSize: [30, 30],
  iconAnchor: [15, 15],
});

// Detection marker icon
const detectionIcon = L.divIcon({
  html: '<div style="width:12px;height:12px;background:#ef4444;border:2px solid white;border-radius:50%;box-shadow:0 0 8px rgba(239,68,68,0.6)"></div>',
  className: '',
  iconSize: [12, 12],
  iconAnchor: [6, 6],
});

// Component to recenter map on drone position
function RecenterMap({ position }) {
  const map = useMap();
  useEffect(() => {
    if (position) {
      map.setView(position, map.getZoom(), { animate: true, duration: 0.5 });
    }
  }, [position, map]);
  return null;
}

export default function DroneMap({ telemetry, detections, flightPath }) {
  const t = telemetry || {};
  const dronePos = t.latitude && t.latitude !== 0
    ? [t.latitude, t.longitude]
    : [47.397742, 8.545594]; // PX4 SITL default home

  const [followDrone, setFollowDrone] = useState(true);

  return (
    <div className="drone-map card">
      <div className="card-header">
        <span>🗺️ Map View</span>
        <label style={{ fontSize: '11px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
          <input
            type="checkbox"
            checked={followDrone}
            onChange={(e) => setFollowDrone(e.target.checked)}
            style={{ accentColor: '#3b82f6' }}
          />
          Follow
        </label>
      </div>
      <div className="card-body">
        <MapContainer
          center={dronePos}
          zoom={17}
          style={{ height: '100%', width: '100%' }}
          attributionControl={false}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {followDrone && <RecenterMap position={dronePos} />}

          {/* Drone marker */}
          <Marker position={dronePos} icon={droneIcon}>
            <Popup>
              <strong>Drone</strong><br />
              Alt: {t.altitude_m?.toFixed(1) || 0}m<br />
              Speed: {t.groundspeed_ms?.toFixed(1) || 0} m/s<br />
              Heading: {t.heading_deg?.toFixed(0) || 0}°
            </Popup>
          </Marker>

          {/* Flight path */}
          {flightPath.length > 1 && (
            <Polyline
              positions={flightPath}
              pathOptions={{
                color: '#3b82f6',
                weight: 2,
                opacity: 0.7,
                dashArray: '6 4',
              }}
            />
          )}

          {/* Detection markers */}
          {detections.map((det, i) => (
            <Marker
              key={det.id || i}
              position={[det.latitude, det.longitude]}
              icon={detectionIcon}
            >
              <Popup>
                <strong>{det.class_name}</strong><br />
                Confidence: {(det.confidence * 100).toFixed(0)}%<br />
                Track ID: #{det.track_id}
              </Popup>
            </Marker>
          ))}

          {/* Geofence circle */}
          <Circle
            center={[47.397742, 8.545594]}
            radius={500}
            pathOptions={{
              color: '#a855f7',
              weight: 1,
              opacity: 0.4,
              fillOpacity: 0.02,
              dashArray: '8 6',
            }}
          />
        </MapContainer>
      </div>
    </div>
  );
}
