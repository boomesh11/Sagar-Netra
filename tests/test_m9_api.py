"""
Unit and integration tests for Milestone 9:
- SurveyStore SQLite persistence and operator review audit log
- Multi-format report exports (JSON, CSV, GeoJSON, KML, ReportLab PDF)
- FastAPI REST endpoints
- Disaster Mode comparison endpoint
- Live WebSocket waterfall stream
"""
from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient

from backend.sagarnetra.api.app import app
from backend.sagarnetra.api.store import SurveyStore
from backend.sagarnetra.report.generator import (
    export_csv,
    export_geojson,
    export_json,
    export_kml,
    export_pdf,
)


@pytest.fixture
def temp_store(tmp_path: Path) -> SurveyStore:
    db_file = tmp_path / "test_store.db"
    return SurveyStore(db_path=db_file)


def test_survey_store_crud(temp_store: SurveyStore):
    """Validates survey creation, detection persistence, and operator review recording."""
    # 1. Create survey
    srv = temp_store.create_survey(
        survey_id="SRV_CHENNAI_01",
        site_name="Chennai Outer Anchorage",
        swath_range_m=75.0,
        altitude_m=10.0,
    )
    assert srv["survey_id"] == "SRV_CHENNAI_01"

    # 2. Save detections
    temp_store.save_detection(
        target_id="TGT_001",
        survey_id="SRV_CHENNAI_01",
        class_name="ghost_net",
        hazard_confidence=82.5,
        status="CONFIRMED_HAZARD",
        priority=0.825,
        lat=13.085,
        lon=80.298,
        utm_easting=416200.0,
        utm_northing=1448500.0,
        zone=44,
        r95_m=3.2,
        length_m=12.5,
        width_m=2.4,
        height_m=0.8,
        orientation_deg=45.0,
        views=2,
        components={"p_cal": 0.85, "V_phys": 0.75},
        rules=[{"rule_id": "R1", "score": 1, "reason": "Height consistent"}],
    )

    temp_store.save_detection(
        target_id="TGT_002",
        survey_id="SRV_CHENNAI_01",
        class_name="rock_cluster",
        hazard_confidence=22.0,
        status="CONFUSER_REJECTED",
        priority=0.015,
        lat=13.086,
        lon=80.299,
        utm_easting=416300.0,
        utm_northing=1448600.0,
        zone=44,
        r95_m=4.1,
        length_m=3.0,
        width_m=2.0,
    )

    # 3. Retrieve and filter
    all_dets = temp_store.get_detections(survey_id="SRV_CHENNAI_01")
    assert len(all_dets) == 2

    confirmed = temp_store.get_detections(survey_id="SRV_CHENNAI_01", status="CONFIRMED_HAZARD")
    assert len(confirmed) == 1
    assert confirmed[0]["target_id"] == "TGT_001"

    # 4. Operator Review
    rev = temp_store.record_operator_review(
        target_id="TGT_001",
        action="CONFIRMED",
        operator_notes="Verified float chain regularity on Starboard pass",
    )
    assert rev["action"] == "CONFIRMED"

    det_detail = temp_store.get_detection_by_id("TGT_001")
    assert det_detail is not None
    assert det_detail["review_status"] == "CONFIRMED"
    assert len(det_detail["reviews"]) == 1

    # 5. Survey Summary Stats
    summary = temp_store.get_survey_summary("SRV_CHENNAI_01")
    assert summary["total_targets"] == 2
    assert summary["confirmed_count"] == 1
    assert summary["confuser_count"] == 1
    assert summary["reviewed_count"] == 1


def test_report_exports(tmp_path: Path):
    """Validates multi-format report exports: JSON, CSV, GeoJSON, KML, and ReportLab PDF."""
    sample_targets = [
        {
            "target_id": "TGT_001",
            "class_name": "ghost_net",
            "status": "CONFIRMED_HAZARD",
            "priority": 0.85,
            "hazard_confidence": 86.4,
            "lat": 13.0827,
            "lon": 80.2707,
            "utm_easting": 416250.0,
            "utm_northing": 1448500.0,
            "zone": 44,
            "r95_m": 3.2,
            "length_m": 14.2,
            "width_m": 2.5,
            "height_m": 0.9,
            "orientation_deg": 35.0,
            "views": 2,
            "review_status": "CONFIRMED",
        },
        {
            "target_id": "TGT_002",
            "class_name": "cylinder",
            "status": "SUSPECTED_HAZARD",
            "priority": 0.48,
            "hazard_confidence": 54.0,
            "lat": 13.0840,
            "lon": 80.2720,
            "utm_easting": 416400.0,
            "utm_northing": 1448650.0,
            "zone": 44,
            "r95_m": 4.5,
            "length_m": 1.8,
            "width_m": 0.8,
            "height_m": 0.7,
            "orientation_deg": 80.0,
            "views": 1,
            "review_status": "UNREVIEWED",
        }
    ]
    meta = {"survey_id": "SRV_TEST", "site_name": "Chennai Port"}

    # 1. JSON Export
    json_str = export_json(sample_targets, survey_meta=meta)
    parsed_json = json.loads(json_str)
    assert parsed_json["target_count"] == 2
    assert len(parsed_json["targets"]) == 2

    # 2. CSV Export
    csv_str = export_csv(sample_targets)
    assert "target_id,class_name,status" in csv_str
    assert "TGT_001,ghost_net,CONFIRMED_HAZARD" in csv_str
    assert "6.4" in csv_str  # search_box_side_m = 2 * 3.2

    # 3. GeoJSON Export
    geojson_str = export_geojson(sample_targets)
    geo_data = json.loads(geojson_str)
    assert geo_data["type"] == "FeatureCollection"
    # Should have 2 point pins + 2 error ellipse polygons = 4 features
    assert len(geo_data["features"]) == 4

    # 4. KML Export
    kml_str = export_kml(sample_targets)
    assert "<kml" in kml_str
    assert "<Placemark>" in kml_str
    assert "TGT_001" in kml_str

    # 5. PDF Export
    pdf_out = tmp_path / "test_workorder.pdf"
    res_pdf = export_pdf(sample_targets, output_path=pdf_out, survey_meta=meta)
    assert res_pdf.exists()
    assert res_pdf.stat().st_size > 1000  # Multi-page valid PDF


def test_fastapi_rest_endpoints():
    """Validates FastAPI routes using HTTP TestClient."""
    client = TestClient(app)

    # 1. Health check
    resp_health = client.get("/api/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "HEALTHY"

    # 2. Create and list surveys
    resp_create = client.post("/api/surveys", json={
        "survey_id": "SRV_TEST_API_01",
        "site_name": "Visakhapatnam Channel",
        "swath_range_m": 60.0,
        "altitude_m": 8.0,
    })
    assert resp_create.status_code == 200

    resp_surveys = client.get("/api/surveys")
    assert resp_surveys.status_code == 200
    assert any(s["survey_id"] == "SRV_TEST_API_01" for s in resp_surveys.json())

    # 3. Detections query
    resp_dets = client.get("/api/surveys/SRV_TEST_API_01/detections")
    assert resp_dets.status_code == 200

    # 4. Disaster scenarios and comparison
    resp_scenarios = client.get("/api/disaster/scenarios")
    assert resp_scenarios.status_code == 200
    assert len(resp_scenarios.json()) >= 3

    resp_compare = client.post("/api/disaster/compare", json={
        "scenario_name": "chennai_port_basin",
        "diff_threshold": 0.45,
    })
    assert resp_compare.status_code == 200
    data_compare = resp_compare.json()
    assert "obstructions" in data_compare
    assert data_compare["total_new_obstructions"] >= 1

    # 5. Report download endpoint
    resp_report_json = client.get("/api/surveys/SRV_TEST_API_01/reports/json")
    assert resp_report_json.status_code == 200
    assert "application/json" in resp_report_json.headers["content-type"]

    resp_report_csv = client.get("/api/surveys/SRV_TEST_API_01/reports/csv")
    assert resp_report_csv.status_code == 200
    assert "text/csv" in resp_report_csv.headers["content-type"]


def test_websocket_waterfall_stream():
    """Validates real-time live waterfall ping streaming via WebSocket."""
    client = TestClient(app)

    with client.websocket_connect("/ws/waterfall") as websocket:
        # Read first 3 streamed pings
        for i in range(1, 4):
            data = websocket.receive_json()
            assert data["ping_number"] == i
            assert "timestamp" in data
            assert len(data["port_samples"]) > 0
            assert len(data["stbd_samples"]) > 0
            assert isinstance(data["detections"], list)
