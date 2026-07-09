import React from 'react';

export default function MissionControl({
  missionState, onStart, onAbort, onRTL, onDownloadCSV, onDownloadPDF,
}) {
  const isIdle = missionState === 'IDLE' || missionState === 'LANDED';
  const isActive = !isIdle;

  return (
    <div className="mission-control">
      <button
        className="btn btn-start"
        onClick={onStart}
        disabled={isActive}
      >
        ▶ Start Mission
      </button>

      <button
        className="btn btn-abort"
        onClick={onAbort}
        disabled={isIdle}
      >
        ⏹ Abort
      </button>

      <button
        className="btn btn-rtl"
        onClick={onRTL}
        disabled={isIdle}
      >
        🏠 RTL
      </button>

      <div style={{ width: 1, height: 28, background: 'rgba(255,255,255,0.1)', margin: '0 8px' }} />

      <button className="btn btn-report" onClick={onDownloadPDF}>
        📄 PDF Report
      </button>

      <button className="btn btn-report" onClick={onDownloadCSV}>
        📊 CSV Export
      </button>
    </div>
  );
}
