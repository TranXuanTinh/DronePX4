"""
Video Router — WebSocket MJPEG streaming endpoint.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response

from src.dashboard.backend.dependencies import container

logger = logging.getLogger(__name__)

router = APIRouter(tags=["video"])


@router.websocket("/ws/video")
async def ws_video(websocket: WebSocket):
    """Stream MJPEG video frames with detection overlays."""
    await websocket.accept()
    video_server = container.video_server

    await video_server.register_client(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await video_server.unregister_client(websocket)


@router.get("/api/snapshot")
async def get_snapshot():
    """Get a single JPEG snapshot from the camera."""
    video_server = container.video_server
    data = video_server.get_snapshot()
    if data is None:
        raise HTTPException(503, "Camera not available")
    return Response(content=data, media_type="image/jpeg")
