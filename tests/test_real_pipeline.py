"""
tests/test_real_pipeline.py
===========================
Verifies the complete 20-stage hydrographic sonar pipeline execution:
Real Sonar -> Quality -> Slant Range -> Feature Stack -> CFAR -> SegNet ->
Net Signature -> Physics (R1-R8) -> Confidence -> Geotagging -> Work-Order Reports
"""

import io
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend.sagarnetra.api.app import app

ROOT = Path(__file__).resolve().parent.parent


def test_full_pipeline_with_navigation_metadata():
    """
    Test uploading a survey file with valid navigation sidecar.
    Verifies that all 20 stages run, coordinates are derived via WGS84/UTM,
    honest r95 is computed, and all 5 report formats export cleanly.
    """
    client = TestClient(app)

    # 1. Load real sonar fixture image and navigation sidecar
    with open("tests/fixtures/wreck_real.png", "rb") as f:
        buf_img = io.BytesIO(f.read())
    with open("tests/fixtures/survey_nav_sample.csv", "rb") as f:
        buf_nav = io.BytesIO(f.read())

    # 3. Upload to API
    resp = client.post(
        "/api/upload",
        files={
            "file": ("survey_track_alpha.png", buf_img, "image/png"),
            "nav_file": ("survey_track_alpha_nav.csv", buf_nav, "text/csv")
        },
        data={"survey_id": "SRV_HYDRO_REAL_01", "site_name": "Bay_Of_Bengal_Shelf"}
    )

    assert resp.status_code == 200, f"Upload error: {resp.text}"
    data = resp.json()

    # 4. Pipeline stages check
    assert data["status"] == "ANALYSIS_COMPLETE"
    assert data["mode"] == "HYDROGRAPHIC_SURVEY"
    assert len(data["pipeline_stages"]) == 20
    assert data["pipeline_stages"][0]["name"] == "INGESTING"
    assert data["pipeline_stages"][19]["name"] == "REPORT"

    # 5. Geolocation check
    target = data["targets"][0]
    pos = target["position"]
    assert pos["position_status"] == "AVAILABLE"
    assert pos["lat"] is not None
    assert pos["lon"] is not None
    assert pos["r95_m"] is not None and pos["r95_m"] > 0

    # 6. Target Inspector multi-layer check
    tid = target["target_id"]
    layers_resp = client.get(f"/api/targets/{tid}/layers")
    assert layers_resp.status_code == 200
    layers_data = layers_resp.json()
    assert layers_data["alignment_verified"] is True
    assert len(layers_data["layers_available"]) == 8

    # 7. Multi-format export check
    for fmt in ["json", "csv", "geojson", "kml", "pdf"]:
        export_resp = client.get(f"/api/surveys/SRV_HYDRO_REAL_01/reports/{fmt}")
        assert export_resp.status_code == 200, f"Export format {fmt} failed"
        assert len(export_resp.content) > 0
