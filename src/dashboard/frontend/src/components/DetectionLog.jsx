import React, { useRef, useEffect } from 'react';

export default function DetectionLog({ detections }) {
  const scrollRef = useRef(null);

  // Auto-scroll to bottom on new detection
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [detections.length]);

  function getClassBadge(cls) {
    const c = (cls || '').toLowerCase();
    const known = ['person', 'car', 'truck', 'vehicle', 'damage'];
    const badgeClass = known.includes(c) ? c : 'default';
    return <span className={`class-badge ${badgeClass}`}>{cls}</span>;
  }

  function formatTime(timestamp) {
    if (!timestamp) return '—';
    const d = new Date(timestamp * 1000);
    return d.toLocaleTimeString('en-US', { hour12: false });
  }

  function getConfBar(conf) {
    const pct = Math.min(100, conf * 100);
    const cls = pct >= 80 ? 'confidence-high' : pct >= 50 ? 'confidence-mid' : 'confidence-low';
    return (
      <span>
        {(conf * 100).toFixed(0)}%
        <span className="confidence-bar">
          <span className={`confidence-bar-fill ${cls}`} style={{ width: `${pct}%` }} />
        </span>
      </span>
    );
  }

  return (
    <div className="detection-log card">
      <div className="card-header">
        <span>📋 Detection Log ({detections.length})</span>
      </div>
      <div className="card-body" ref={scrollRef}>
        {detections.length === 0 ? (
          <div className="empty-state">
            <div className="icon">🔍</div>
            <div>No detections yet</div>
            <div style={{ fontSize: '11px' }}>Detections will appear here during search</div>
          </div>
        ) : (
          <table className="detection-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Time</th>
                <th>Class</th>
                <th>Confidence</th>
                <th>GPS</th>
              </tr>
            </thead>
            <tbody>
              {detections.map((det, i) => (
                <tr key={det.id || i}>
                  <td style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '11px' }}>
                    {det.id || `DET-${i+1}`}
                  </td>
                  <td style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                    {formatTime(det.timestamp)}
                  </td>
                  <td>{getClassBadge(det.class_name)}</td>
                  <td>{getConfBar(det.confidence)}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: '10px', color: '#94a3b8' }}>
                    {det.latitude?.toFixed(5)}, {det.longitude?.toFixed(5)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
