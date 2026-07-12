"""
Reports Router — PDF and CSV report generation endpoints.
"""
from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from src.dashboard.backend.dependencies import container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/report", tags=["reports"])


@router.get("/csv")
async def generate_csv_report():
    """Generate and download CSV detection report.

    Returns a CSV with headers even when there are no detections,
    so the user always gets a downloadable file.
    """
    detections = container.detections

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "timestamp", "detection_id", "track_id", "class",
        "confidence", "latitude", "longitude", "altitude_m",
    ])

    if detections:
        for i, d in enumerate(detections):
            writer.writerow([
                d.timestamp, f"DET-{i + 1:03d}", d.track_id, d.class_name,
                f"{d.confidence:.3f}", f"{d.latitude_deg:.6f}",
                f"{d.longitude_deg:.6f}", f"{d.drone_altitude_m:.1f}",
            ])
    else:
        # Add an informational row so the CSV isn't completely empty
        writer.writerow([
            "", "", "", "No detections recorded",
            "", "", "", "",
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
    connector = container.connector

    report_dir = Path(
        config.get("logging", {}).get("report_dir", "data/reports"),
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "mission_report.pdf"

    # Gather telemetry data for the report
    telemetry_data = None
    if connector and connector.latest_telemetry:
        telem = connector.latest_telemetry
        telemetry_data = {
            "latitude": telem.position.latitude_deg,
            "longitude": telem.position.longitude_deg,
            "altitude_m": telem.position.relative_altitude_m,
            "heading_deg": telem.heading_deg,
            "groundspeed_ms": telem.groundspeed_ms,
            "battery_percent": telem.battery_percent,
            "battery_voltage": telem.battery_voltage,
            "flight_mode": telem.flight_mode,
            "armed": telem.armed,
            "gps_satellites": telem.gps_num_satellites,
            "gps_fix_type": telem.gps_fix_type,
            "is_connected": telem.is_connected,
        }

    try:
        generate_pdf(
            output_path=str(report_path),
            detections=detections,
            mission_duration_s=sm.mission_elapsed_s,
            waypoint_count=len(sm.waypoints),
            telemetry_data=telemetry_data,
        )
        return FileResponse(
            path=str(report_path),
            media_type="application/pdf",
            filename="mission_report.pdf",
        )
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}")
