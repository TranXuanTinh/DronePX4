"""
Reports Router — PDF and CSV report generation endpoints.
"""
from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.dashboard.backend.dependencies import container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/report", tags=["reports"])


@router.get("/csv")
async def generate_csv_report():
    """Generate and download CSV detection report."""
    detections = container.detections
    if not detections:
        raise HTTPException(404, "No detections to report")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "timestamp", "detection_id", "track_id", "class",
        "confidence", "latitude", "longitude", "altitude_m",
    ])
    for i, d in enumerate(detections):
        writer.writerow([
            d.timestamp, f"DET-{i + 1:03d}", d.track_id, d.class_name,
            f"{d.confidence:.3f}", f"{d.latitude_deg:.6f}",
            f"{d.longitude_deg:.6f}", f"{d.drone_altitude_m:.1f}",
        ])

    report_dir = Path(
        container.config.get("logging", {}).get(
            "report_dir", "data/reports",
        )
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "detection_report.csv"
    report_path.write_text(output.getvalue())

    return FileResponse(
        path=str(report_path),
        media_type="text/csv",
        filename="detection_report.csv",
    )


@router.get("/pdf")
async def generate_pdf_report():
    """Generate and download PDF mission report."""
    from src.dashboard.backend.api.reports import generate_pdf

    detections = container.detections
    sm = container.state_machine
    config = container.config

    report_dir = Path(
        config.get("logging", {}).get("report_dir", "data/reports"),
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "mission_report.pdf"

    try:
        generate_pdf(
            output_path=str(report_path),
            detections=detections,
            mission_duration_s=sm.mission_elapsed_s,
            waypoint_count=len(sm.waypoints),
        )
        return FileResponse(
            path=str(report_path),
            media_type="application/pdf",
            filename="mission_report.pdf",
        )
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}")
