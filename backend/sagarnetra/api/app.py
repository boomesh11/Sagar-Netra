"""
SagarNetra API — FastAPI Service with Live WebSocket Streaming & REST Endpoints.
Serves:
  - REST endpoints for surveys, detections, operator reviews, clearance maps, and reports
  - Multi-format report downloads: JSON, CSV, GeoJSON, KML, and PDF
  - Disaster Mode pre/post cyclone change comparison
  - Real-time WebSocket streaming of dual port/starboard waterfall pings and detections
"""
from __future__ import annotations

import asyncio
import io
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from backend.sagarnetra.api.store import SurveyStore
from backend.sagarnetra.change.disaster import DisasterChangeDetector, create_synthetic_disaster_scenario
from backend.sagarnetra.coverage.pod_map import ClearanceGridMap
from backend.sagarnetra.report.generator import (
    export_csv,
    export_geojson,
    export_json,
    export_kml,
    export_pdf,
)

app = FastAPI(
    title="SagarNetra — Underwater Debris Intelligence API",
    description="Physics-grounded side-scan sonar detection, geotagging, clearance mapping & disaster change detection",
    version="1.0.0",
)

# Enable CORS for React frontend (Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent Store instance
store = SurveyStore()


# --- Pydantic Request Models ---
class CreateSurveyRequest(BaseModel):
    survey_id: str
    site_name: str
    swath_range_m: float = 60.0
    altitude_m: float = 8.0


class OperatorReviewRequest(BaseModel):
    action: str = Field(..., description="CONFIRMED, REJECTED, CHANGED_CLASS, UNSURE")
    new_class: Optional[str] = None
    notes: Optional[str] = None


class DisasterCompareRequest(BaseModel):
    scenario_name: str = "chennai_port_basin"
    diff_threshold: float = 0.45


# --- REST Endpoints ---
@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    return {
        "status": "HEALTHY",
        "service": "SagarNetra API",
        "version": "1.0.0",
        "device": "cpu",
        "db_connected": store.db_path.exists(),
    }


@app.get("/api/surveys")
def list_surveys() -> List[Dict[str, Any]]:
    with store._get_connection() as conn:
        rows = conn.execute("SELECT * FROM surveys ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


@app.post("/api/surveys")
def create_survey(req: CreateSurveyRequest) -> Dict[str, Any]:
    return store.create_survey(
        survey_id=req.survey_id,
        site_name=req.site_name,
        swath_range_m=req.swath_range_m,
        altitude_m=req.altitude_m,
    )


@app.get("/api/surveys/{survey_id}/detections")
def get_detections(
    survey_id: str,
    status: Optional[str] = None,
    min_confidence: float = Query(0.0, ge=0.0, le=100.0),
) -> List[Dict[str, Any]]:
    return store.get_detections(survey_id=survey_id, status=status, min_confidence=min_confidence)


@app.get("/api/surveys/{survey_id}/detections/{target_id}")
def get_detection_detail(survey_id: str, target_id: str) -> Dict[str, Any]:
    det = store.get_detection_by_id(target_id)
    if not det:
        raise HTTPException(status_code=404, detail=f"Target {target_id} not found")
    return det


@app.post("/api/surveys/{survey_id}/detections/{target_id}/review")
def submit_operator_review(
    survey_id: str,
    target_id: str,
    req: OperatorReviewRequest,
) -> Dict[str, Any]:
    det = store.get_detection_by_id(target_id)
    if not det:
        raise HTTPException(status_code=404, detail=f"Target {target_id} not found")

    return store.record_operator_review(
        target_id=target_id,
        action=req.action,
        new_class=req.new_class,
        operator_notes=req.notes,
    )


@app.get("/api/surveys/{survey_id}/clearance")
def get_clearance_map(survey_id: str) -> Dict[str, Any]:
    summary = store.get_survey_summary(survey_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Survey {survey_id} not found")

    # Generate grid clearance metrics
    grid = ClearanceGridMap(origin_easting=416000.0, origin_northing=1448000.0, width_m=500.0, height_m=500.0)
    grid.record_swath(416250.0, 1448000.0, 416250.0, 1448500.0, altitude_m=8.0, range_m=60.0)

    detections = store.get_detections(survey_id=survey_id)
    for d in detections:
        grid.mark_target(d["utm_easting"], d["utm_northing"])

    clearance_data = grid.get_clearance_summary()
    clearance_data["survey_id"] = survey_id
    clearance_data["total_targets"] = len(detections)
    return clearance_data


@app.get("/api/surveys/{survey_id}/reports/{fmt}")
def download_report(survey_id: str, fmt: str):
    detections = store.get_detections(survey_id=survey_id)
    summary = store.get_survey_summary(survey_id)
    meta = {
        "survey_id": survey_id,
        "site_name": summary.get("site_name", "Survey Site"),
        "date": summary.get("created_at", "2026-09-26")[:10],
    }

    fmt = fmt.lower()
    if fmt == "json":
        content = export_json(detections, survey_meta=meta)
        return Response(content=content, media_type="application/json", headers={"Content-Disposition": f"attachment; filename=sagarnetra_{survey_id}.json"})

    elif fmt == "csv":
        content = export_csv(detections)
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=sagarnetra_{survey_id}.csv"})

    elif fmt in ["geojson", "geo.json"]:
        content = export_geojson(detections)
        return Response(content=content, media_type="application/geo+json", headers={"Content-Disposition": f"attachment; filename=sagarnetra_{survey_id}.geojson"})

    elif fmt == "kml":
        content = export_kml(detections)
        return Response(content=content, media_type="application/vnd.google-earth.kml+xml", headers={"Content-Disposition": f"attachment; filename=sagarnetra_{survey_id}.kml"})

    elif fmt == "pdf":
        pdf_path = Path(f"artifacts/reports/workorder_{survey_id}.pdf")
        export_pdf(detections, output_path=pdf_path, survey_meta=meta)
        return FileResponse(path=str(pdf_path), media_type="application/pdf", filename=f"sagarnetra_workorder_{survey_id}.pdf")

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format '{fmt}'. Supported: json, csv, geojson, kml, pdf")


# --- Disaster Mode Endpoints ---
@app.get("/api/disaster/scenarios")
def list_disaster_scenarios() -> List[Dict[str, Any]]:
    return [
        {"id": "chennai_port_basin", "name": "Chennai Port Basin (Post-Michaung)", "lat": 13.085, "lon": 80.298, "utm_zone": 44},
        {"id": "kochi_channel", "name": "Kochi Shipping Channel (Post-Monsoon)", "lat": 9.965, "lon": 76.241, "utm_zone": 43},
        {"id": "visakhapatnam_harbour", "name": "Visakhapatnam Fishing Harbour (Post-Hudhud)", "lat": 17.695, "lon": 83.301, "utm_zone": 44},
    ]


@app.post("/api/disaster/compare")
def run_disaster_compare(req: DisasterCompareRequest) -> Dict[str, Any]:
    base_img, post_img, meta = create_synthetic_disaster_scenario(req.scenario_name)
    detector = DisasterChangeDetector(zone=meta["utm_zone"])

    obstructions = detector.detect_changes(
        baseline_img=base_img,
        post_disaster_img=post_img,
        origin_easting=meta["origin_utm"][0],
        origin_northing=meta["origin_utm"][1],
        diff_threshold=req.diff_threshold,
    )

    results = []
    for obs in obstructions:
        results.append({
            "obstruction_id": obs.obstruction_id,
            "change_type": obs.change_type.value,
            "class_name": obs.estimated_class,
            "lat": obs.lat,
            "lon": obs.lon,
            "utm_easting": obs.utm_easting,
            "utm_northing": obs.utm_northing,
            "dimensions": {
                "length_m": obs.dimensions.length_m,
                "width_m": obs.dimensions.width_m,
                "height_m": obs.dimensions.height_m,
                "area_m2": obs.dimensions.area_m2,
            },
            "r95_m": obs.r95_m,
            "hazard_confidence": obs.confidence.score,
            "priority": obs.confidence.priority,
            "status": obs.confidence.status.value,
            "delta_intensity": obs.delta_intensity,
            "description": obs.description,
        })

    return {
        "scenario": req.scenario_name,
        "site_name": meta["site_name"],
        "baseline_date": meta["baseline_date"],
        "post_cyclone_date": meta["post_cyclone_date"],
        "total_new_obstructions": len(results),
        "obstructions": results,
    }


# --- Real-Time WebSocket Streaming ---
@app.websocket("/ws/waterfall")
async def websocket_waterfall_stream(websocket: WebSocket):
    """
    Streams simulated dual port/starboard side-scan sonar pings with live detections.
    """
    await websocket.accept()
    rng = np.random.default_rng(42)
    ping_num = 0

    try:
        while True:
            ping_num += 1
            # Generate 512-sample port and starboard across-track intensity profiles
            t = ping_num * 0.1
            bg_noise = rng.gamma(shape=4.0, scale=0.1, size=512).astype(np.float32)

            # Simulated highlight & shadow if target encountered around ping 50
            stbd_samples = bg_noise.copy()
            port_samples = bg_noise.copy()

            detections_this_ping = []
            if 45 <= (ping_num % 100) <= 65:
                # Add ghost net float chain highlight on starboard at sample 220
                stbd_samples[210:235] += 0.75
                stbd_samples[235:280] *= 0.15  # Acoustic shadow
                detections_this_ping.append({
                    "target_id": f"LIVE_{ping_num:04d}",
                    "channel": "stbd",
                    "class_name": "ghost_net",
                    "sample_idx": 220,
                    "confidence": 84.5,
                    "status": "CONFIRMED_HAZARD",
                })

            payload = {
                "ping_number": ping_num,
                "timestamp": t,
                "altitude_m": 8.0 + 0.2 * math.sin(t / 10.0),
                "heading_deg": round((90.0 + 2.0 * math.sin(t / 20.0)) % 360.0, 1),
                "port_samples": np.clip(port_samples * 255.0, 0, 255).astype(int).tolist()[:128],  # Subsampled for network efficiency
                "stbd_samples": np.clip(stbd_samples * 255.0, 0, 255).astype(int).tolist()[:128],
                "detections": detections_this_ping,
            }

            await websocket.send_json(payload)
            await asyncio.sleep(0.08)  # ~12 pings per second live streaming rate

    except WebSocketDisconnect:
        pass
