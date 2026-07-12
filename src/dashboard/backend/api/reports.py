"""
Reports — PDF and CSV report generation for post-mission analysis.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def generate_pdf(
    output_path: str,
    detections: list,
    mission_duration_s: float,
    waypoint_count: int,
    telemetry_data: Optional[dict] = None,
) -> None:
    """Generate a PDF mission report.

    Args:
        output_path: Path to save the PDF file
        detections: List of GeotaggedDetection objects
        mission_duration_s: Total mission duration in seconds
        waypoint_count: Total number of waypoints
        telemetry_data: Optional dict with latest telemetry snapshot
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak,
    )

    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # --- Title ---
    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=24, spaceAfter=20,
    )
    elements.append(Paragraph("Drone Inspection Report", title_style))
    elements.append(Spacer(1, 10))

    # --- Mission Summary ---
    elements.append(Paragraph("Mission Summary", styles["Heading2"]))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    duration_min = mission_duration_s / 60.0

    summary_data = [
        ["Report Generated", now],
        ["Mission Duration", f"{duration_min:.1f} minutes"],
        ["Total Waypoints", str(waypoint_count)],
        ["Total Detections", str(len(detections))],
    ]

    # Count by class
    class_counts: dict[str, int] = {}
    for d in detections:
        class_counts[d.class_name] = class_counts.get(d.class_name, 0) + 1

    for cls, count in sorted(class_counts.items()):
        summary_data.append([f"  {cls}", str(count)])

    summary_table = Table(summary_data, colWidths=[60 * mm, 80 * mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e8e8e8")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # --- Telemetry Summary ---
    if telemetry_data:
        elements.append(
            Paragraph("Vehicle Telemetry (at report time)", styles["Heading2"])
        )

        gps_fix_names = {
            0: "No GPS", 1: "No Fix", 2: "2D Fix",
            3: "3D Fix", 4: "DGPS", 5: "RTK Float", 6: "RTK Fixed",
        }
        fix_type = telemetry_data.get("gps_fix_type", 0)
        fix_name = gps_fix_names.get(fix_type, f"Type {fix_type}")

        telem_rows = [
            ["Parameter", "Value"],
            [
                "Position",
                f"{telemetry_data.get('latitude', 0):.6f}°, "
                f"{telemetry_data.get('longitude', 0):.6f}°",
            ],
            [
                "Altitude",
                f"{telemetry_data.get('altitude_m', 0):.1f} m",
            ],
            [
                "Heading",
                f"{telemetry_data.get('heading_deg', 0):.1f}°",
            ],
            [
                "Ground Speed",
                f"{telemetry_data.get('groundspeed_ms', 0):.1f} m/s",
            ],
            [
                "Battery",
                f"{telemetry_data.get('battery_percent', 0):.0f}% "
                f"({telemetry_data.get('battery_voltage', 0):.1f}V)",
            ],
            [
                "Flight Mode",
                str(telemetry_data.get("flight_mode", "UNKNOWN")),
            ],
            [
                "Armed",
                "Yes" if telemetry_data.get("armed") else "No",
            ],
            [
                "GPS",
                f"{telemetry_data.get('gps_satellites', 0)} satellites "
                f"({fix_name})",
            ],
            [
                "SITL Connected",
                "Yes" if telemetry_data.get("is_connected") else "No",
            ],
        ]

        telem_table = Table(telem_rows, colWidths=[50 * mm, 90 * mm])
        telem_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#e8e8e8")),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f5f5f5")]),
        ]))
        elements.append(telem_table)
        elements.append(Spacer(1, 20))

    # --- Detection Table ---
    if detections:
        elements.append(Paragraph("Detection Log", styles["Heading2"]))

        det_header = ["#", "Class", "Conf", "Latitude", "Longitude", "Alt (m)"]
        det_data = [det_header]

        for i, d in enumerate(detections):
            det_data.append([
                f"DET-{i+1:03d}",
                d.class_name,
                f"{d.confidence:.2f}",
                f"{d.latitude_deg:.6f}",
                f"{d.longitude_deg:.6f}",
                f"{d.drone_altitude_m:.1f}",
            ])

        det_table = Table(det_data, colWidths=[20*mm, 25*mm, 15*mm, 35*mm, 35*mm, 20*mm])
        det_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ]))
        elements.append(det_table)
    else:
        no_det_style = ParagraphStyle(
            "NoDetections", parent=styles["Normal"],
            fontSize=11, textColor=colors.HexColor("#666666"),
            spaceAfter=10,
        )
        elements.append(
            Paragraph(
                "No objects were detected during this mission. "
                "This may indicate the search area was clear, "
                "or the mission was not fully executed.",
                no_det_style,
            )
        )

    elements.append(Spacer(1, 30))
    elements.append(Paragraph(
        "Report generated by Drone Inspector — Simulation",
        styles["Italic"],
    ))

    # Build PDF
    doc.build(elements)
    logger.info(f"PDF report generated: {output_path} ({len(detections)} detections)")
