import React, { useEffect, useRef, useState } from 'react';

export default function VideoFeed({ wsUrl }) {
  const canvasRef = useRef(null);
  const [status, setStatus] = useState('connecting');

  useEffect(() => {
    let ws;
    let reconnectTimer;

    function connect() {
      setStatus('connecting');
      ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {
        setStatus('streaming');
        // Send keepalive
        const interval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, 5000);
        ws._keepalive = interval;
      };

      ws.onclose = () => {
        setStatus('disconnected');
        clearInterval(ws._keepalive);
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();

      ws.onmessage = (event) => {
        const blob = new Blob([event.data], { type: 'image/jpeg' });
        const url = URL.createObjectURL(blob);
        const img = new Image();
        img.onload = () => {
          const canvas = canvasRef.current;
          if (!canvas) return;
          canvas.width = img.width;
          canvas.height = img.height;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0);
          URL.revokeObjectURL(url);
        };
        img.src = url;
      };
    }

    connect();
    return () => {
      clearTimeout(reconnectTimer);
      if (ws) {
        clearInterval(ws._keepalive);
        ws.close();
      }
    };
  }, [wsUrl]);

  return (
    <div className="video-feed card">
      <div className="card-header">
        <span>📹 Live Camera Feed</span>
        <span style={{
          color: status === 'streaming' ? '#22c55e' :
                 status === 'connecting' ? '#eab308' : '#ef4444',
          fontSize: '11px'
        }}>
          ● {status}
        </span>
      </div>
      <div className="card-body">
        {status === 'streaming' ? (
          <canvas ref={canvasRef} />
        ) : (
          <div className="video-placeholder">
            <div className="icon">📡</div>
            <div>{status === 'connecting' ? 'Connecting to camera...' : 'Camera offline'}</div>
          </div>
        )}
      </div>
    </div>
  );
}
