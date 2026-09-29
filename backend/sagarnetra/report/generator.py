"""
SagarNetra Reports — Multi-Format Clearance Work-Order Generator.
Exports operational reports in JSON, CSV, GeoJSON, KML, and ReportLab PDF formats:
  - Ranked target priority list
  - 95% error circle and 2 x r95 diver/ROV search box
  - Confidence components breakdown and physics verification rule logs
"""
from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def export_json(
    targets: List[Dict[str, Any]],
    survey_meta: Optional[Dict[str, Any]] = None,
) -> str:
    """Exports full hierarchical survey and detection report as JSON string with provenance."""
    report_dict = {
        "report_type": "SagarNetra_Clearance_Work_Order",
        "policy": "REAL_DATA_FIRST",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "survey_metadata": survey_meta or {},
        "target_count": len(targets),
        "targets": targets,
    }
    return json.dumps(report_dict, indent=2)


def export_csv(targets: List[Dict[str, Any]]) -> str:
    """Exports tabular dive-log summary as CSV string with explicit source_type."""
    output = io.StringIO()
    fieldnames = [
        "target_id", "class_name", "status", "source_type", "priority", "hazard_confidence",
        "lat", "lon", "utm_easting", "utm_northing", "zone",
        "r95_m", "position_status", "r95_status", "search_box_side_m",
        "length_m", "width_m", "height_m", "height_status",
        "orientation_deg", "views", "review_status"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for tgt in targets:
        row = dict(tgt)
        row["source_type"] = tgt.get("source_type", "REAL")
        row["position_status"] = tgt.get("position_status", "AVAILABLE")
        row["r95_status"] = tgt.get("r95_status", "AVAILABLE")
        row["height_status"] = tgt.get("height_status", "AVAILABLE")

        if tgt.get("r95_m") is not None:
            r95 = float(tgt.get("r95_m", 3.0))
            row["search_box_side_m"] = round(2.0 * r95, 2)
        else:
            row["search_box_side_m"] = "UNAVAILABLE"

        writer.writerow(row)

    return output.getvalue()


def export_geojson(
    targets: List[Dict[str, Any]],
    second_look_lines: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Exports GeoJSON FeatureCollection with point pins, r95 error circles, and second-look lines."""
    features = []

    for tgt in targets:
        if tgt.get("lat") is None or tgt.get("lon") is None:
            continue
        lat = float(tgt["lat"])
        lon = float(tgt["lon"])
        r95 = float(tgt.get("r95_m", 3.0)) if tgt.get("r95_m") is not None else 3.0
        tid = tgt.get("target_id", "TGT")

        # 1. Point Feature (Target pin)
        point_feat = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "feature_type": "target_pin",
                "target_id": tid,
                "source_type": tgt.get("source_type", "REAL"),
                "class_name": tgt.get("class_name"),
                "status": tgt.get("status"),
                "priority": tgt.get("priority"),
                "confidence": tgt.get("hazard_confidence"),
                "r95_m": r95,
                "diver_search_box_m": round(2.0 * r95, 2) if r95 is not None else "UNAVAILABLE",
                "length_m": tgt.get("length_m"),
                "width_m": tgt.get("width_m"),
                "height_m": tgt.get("height_m"),
                "position_status": tgt.get("position_status", "AVAILABLE"),
                "position_reason": tgt.get("position_reason"),
                "height_status": tgt.get("height_status", "AVAILABLE"),
                "height_reason": tgt.get("height_reason"),
                "views": tgt.get("views", 1),
            }
        }
        features.append(point_feat)

        # 2. Polygon Feature (Circular 95% error probable area)
        # Generate 24-point circle in geographic coordinates
        lat_rad = math.radians(lat)
        deg_lat = r95 / 111320.0
        deg_lon = r95 / (111320.0 * math.cos(lat_rad))

        circle_pts = []
        for angle in range(0, 361, 15):
            rad = math.radians(angle)
            p_lon = lon + deg_lon * math.cos(rad)
            p_lat = lat + deg_lat * math.sin(rad)
            circle_pts.append([round(p_lon, 7), round(p_lat, 7)])

        polygon_feat = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [circle_pts],
            },
            "properties": {
                "feature_type": "error_ellipse_r95",
                "target_id": tid,
                "r95_m": r95,
            }
        }
        features.append(polygon_feat)

    # 3. LineString Features (Second-look survey tracks)
    if second_look_lines:
        for line in second_look_lines:
            s_lat, s_lon = line["start_latlon"]
            e_lat, e_lon = line["end_latlon"]
            line_feat = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[s_lon, s_lat], [e_lon, e_lat]],
                },
                "properties": {
                    "feature_type": "second_look_line",
                    "line_id": line.get("line_id"),
                    "target_id": line.get("target_id"),
                    "heading_deg": line.get("heading_deg"),
                    "length_m": line.get("length_m"),
                }
            }
            features.append(line_feat)

    collection = {
        "type": "FeatureCollection",
        "features": features,
    }
    return json.dumps(collection, indent=2)


def export_kml(targets: List[Dict[str, Any]]) -> str:
    """Exports Google Earth KML format with styled placemarks."""
    kml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        '  <name>SagarNetra Marine Debris Hazards</name>',
        '  <Style id="hazardConfirmed"><IconStyle><color>ff0000ff</color><scale>1.2</scale></IconStyle></Style>',
        '  <Style id="hazardSuspected"><IconStyle><color>ff00a5ff</color><scale>1.0</scale></IconStyle></Style>',
    ]

    for tgt in targets:
        if tgt.get("lat") is None or tgt.get("lon") is None:
            continue
        lat = tgt["lat"]
        lon = tgt["lon"]
        tid = tgt.get("target_id", "TGT")
        cls_name = tgt.get("class_name", "debris")
        conf = tgt.get("hazard_confidence", 0.0)
        prio = tgt.get("priority", 0.0)
        r95 = tgt.get("r95_m", 3.0) or 3.0

        style_id = "hazardConfirmed" if tgt.get("status") == "CONFIRMED_HAZARD" else "hazardSuspected"
        desc = (
            f"Class: {cls_name}<br/>"
            f"Confidence: {conf}%<br/>"
            f"Priority Score: {prio}<br/>"
            f"95% Error Radius: {r95} m<br/>"
            f"Diver Search Box: {2.0 * r95:.1f} m"
        )

        kml_parts.append(f"""
  <Placemark>
    <name>{tid} ({cls_name})</name>
    <description><![CDATA[{desc}]]></description>
    <styleUrl>#{style_id}</styleUrl>
    <Point>
      <coordinates>{lon},{lat},0</coordinates>
    </Point>
  </Placemark>
        """)

    kml_parts.extend(['</Document>', '</kml>'])
    return "\n".join(kml_parts)


def export_pdf(
    targets: List[Dict[str, Any]],
    output_path: str | Path,
    survey_meta: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Renders a multi-page clearance work-order PDF using ReportLab.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0A2540"),
        alignment=0,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
    )
    h2_style = ParagraphStyle(
        "Heading2",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0A2540"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#2D3748"),
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
    )

    story = []

    # 1. Header & Title Banner
    story.append(Paragraph("SagarNetra — Marine Debris Clearance Work Order", title_style))
    story.append(Paragraph("National Institute of Ocean Technology (NIOT) | Ministry of Earth Sciences (MoES)", subtitle_style))
    story.append(Spacer(1, 10))

    # 2. Survey Overview Metadata
    meta = survey_meta or {}
    site_name = meta.get("site_name", "Operational Coastal Sector")
    survey_id = meta.get("survey_id", "SRV-2026-001")
    date_str = meta.get("date", datetime.now().strftime("%Y-%m-%d"))

    confirmed_count = sum(1 for t in targets if t.get("status") == "CONFIRMED_HAZARD")
    suspected_count = sum(1 for t in targets if t.get("status") == "SUSPECTED_HAZARD")

    summary_data = [
        [Paragraph("<b>Survey ID:</b>", table_cell), Paragraph(str(survey_id), table_cell),
         Paragraph("<b>Survey Date:</b>", table_cell), Paragraph(str(date_str), table_cell)],
        [Paragraph("<b>Operational Site:</b>", table_cell), Paragraph(str(site_name), table_cell),
         Paragraph("<b>Total Targets:</b>", table_cell), Paragraph(str(len(targets)), table_cell)],
        [Paragraph("<b>Confirmed Hazards:</b>", table_cell), Paragraph(f"<font color='red'><b>{confirmed_count}</b></font>", table_cell),
         Paragraph("<b>Suspected Hazards:</b>", table_cell), Paragraph(f"<font color='orange'><b>{suspected_count}</b></font>", table_cell)],
    ]

    t_summary = Table(summary_data, colWidths=[110, 160, 110, 160])
    t_summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 14))

    # 3. Ranked Priority Target Clearance Table
    story.append(Paragraph("Priority Ranked Target Clearance Manifest", h2_style))

    table_headers = [
        Paragraph("<b>Rank</b>", table_cell),
        Paragraph("<b>Target ID</b>", table_cell),
        Paragraph("<b>Source</b>", table_cell),
        Paragraph("<b>Class</b>", table_cell),
        Paragraph("<b>Status</b>", table_cell),
        Paragraph("<b>Conf</b>", table_cell),
        Paragraph("<b>Priority</b>", table_cell),
        Paragraph("<b>Latitude</b>", table_cell),
        Paragraph("<b>Longitude</b>", table_cell),
        Paragraph("<b>r95 (m)</b>", table_cell),
        Paragraph("<b>Search Box</b>", table_cell),
    ]

    rows = [table_headers]
    sorted_targets = sorted(targets, key=lambda x: x.get("priority", 0.0), reverse=True)

    for rank, tgt in enumerate(sorted_targets, 1):
        r95 = float(tgt.get("r95_m", 3.0)) if tgt.get("r95_m") is not None else 3.0
        box_side = f"{2.0 * r95:.1f} m" if tgt.get("r95_m") is not None else "UNAVAIL"
        status_str = tgt.get("status", "CANDIDATE")
        status_color = "#E53E3E" if status_str == "CONFIRMED_HAZARD" else "#DD6B20"
        src_str = tgt.get("source_type", "REAL")

        row = [
            Paragraph(f"<b>#{rank}</b>", table_cell),
            Paragraph(str(tgt.get("target_id", f"TGT_{rank:03d}")), table_cell),
            Paragraph(f"<b>{src_str}</b>", table_cell),
            Paragraph(str(tgt.get("class_name", "hazard")), table_cell),
            Paragraph(f"<font color='{status_color}'><b>{status_str}</b></font>", table_cell),
            Paragraph(f"{tgt.get('hazard_confidence', 0):.1f}%", table_cell),
            Paragraph(f"<b>{tgt.get('priority', 0):.3f}</b>", table_cell),
            Paragraph(f"{tgt.get('lat', 0.0):.5f}" if tgt.get("lat") is not None else "N/A", table_cell),
            Paragraph(f"{tgt.get('lon', 0.0):.5f}" if tgt.get("lon") is not None else "N/A", table_cell),
            Paragraph(f"±{r95:.1f}" if tgt.get("r95_m") is not None else "N/A", table_cell),
            Paragraph(box_side, table_cell),
        ]
        rows.append(row)

    t_targets = Table(rows, colWidths=[28, 52, 45, 60, 85, 38, 42, 50, 50, 42, 48])
    t_targets.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A2540")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_targets)
    story.append(Spacer(1, 14))

    # 4. Target Evidence Cards for Top Targets
    story.append(Paragraph("Detailed Target Acoustic & Geometry Evidence", h2_style))

    for rank, tgt in enumerate(sorted_targets[:4], 1):  # Detail top 4 targets
        tid = tgt.get("target_id", f"TGT_{rank:03d}")
        cls_name = tgt.get("class_name", "hazard")
        r95 = float(tgt.get("r95_m", 3.0))
        len_m = tgt.get("length_m", 1.0)
        wid_m = tgt.get("width_m", 0.5)
        h_m = tgt.get("height_m")
        h_str = f"{h_m:.2f} m" if h_m is not None else "N/A"

        card_title = f"<b>Target #{rank}: {tid} — {cls_name.upper()}</b> (Priority Score: {tgt.get('priority', 0.0):.3f})"
        story.append(Paragraph(card_title, body_style))

        evidence_text = (
            f"• <b>Position:</b> {tgt.get('lat', 0.0):.6f}°N, {tgt.get('lon', 0.0):.6f}°E (UTM {tgt.get('zone', 44)}: E={tgt.get('utm_easting', 0):.1f}m, N={tgt.get('utm_northing', 0):.1f}m)<br/>"
            f"• <b>Error Budget:</b> 95% Confidence Radius <b>r95 = {r95:.2f} m</b> | Diver/ROV Search Square: <b>{2.0 * r95:.1f} m × {2.0 * r95:.1f} m</b><br/>"
            f"• <b>Dimensions:</b> Length = {len_m:.2f} m, Width = {wid_m:.2f} m, Height (from shadow) = <b>{h_str}</b><br/>"
            f"• <b>Confidence Breakdown:</b> Final = <b>{tgt.get('hazard_confidence', 0):.1f}%</b> | Status = {tgt.get('status')} | Multi-view passes: {tgt.get('views', 1)}"
        )
        story.append(Paragraph(evidence_text, body_style))
        story.append(Spacer(1, 6))

    doc.build(story)
    return output_path
