"""
Test Real-Data-First Production Architecture & Integrity.
Validates:
  - Real dataset registry (data/sources.yaml) & manifests
  - Strict leakage protection between train and test splits
  - Metric source separation (real, hybrid, sim, summary)
  - Indian field data non-fabrication guarantee
  - Ghost net data limitation adherence
  - Real survey ingestion & 8-layer target inspection API
  - Report source provenance tracking
"""

import json
from pathlib import Path
from fastapi.testclient import TestClient
from backend.sagarnetra.api.app import app
from backend.sagarnetra.report.generator import export_csv, export_json, export_geojson
from scripts.check_leakage import check_leakage


def test_sources_yaml_and_manifest():
    """Verify data/sources.yaml and data/dataset_manifest.json exist and specify licenses and class mappings."""
    root_dir = Path(__file__).resolve().parent.parent
    sources_path = root_dir / "data" / "sources.yaml"
    manifest_path = root_dir / "data" / "dataset_manifest.json"

    assert sources_path.exists(), "data/sources.yaml must exist"
    assert manifest_path.exists(), "data/dataset_manifest.json must exist"

    sources_content = sources_path.read_text(encoding="utf-8")
    assert "REAL_DATA_FIRST" in sources_content
    assert "ghostpot" in sources_content
    assert "sctd" in sources_content
    assert "klsg2" in sources_content
    assert "ai4shipwrecks" in sources_content
    assert "noaa_usgs_sss" in sources_content
    assert "GPL-3.0" in sources_content
    assert "MIT" in sources_content

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data.get("policy") == "REAL_DATA_FIRST"
    assert manifest_data.get("primary_source") == "real"


def test_indian_data_honesty():
    """Verify Indian field survey path does not fabricate observations when data is unavailable."""
    root_dir = Path(__file__).resolve().parent.parent
    indian_readme = root_dir / "data" / "real" / "indian" / "README.md"

    assert indian_readme.exists(), "data/real/indian/README.md must exist"
    content = indian_readme.read_text(encoding="utf-8")
    assert "REAL INDIAN FIELD DATA NOT LOADED" in content

    client = TestClient(app)
    response = client.get("/api/datasets/status")
    assert response.status_code == 200
    data = response.json()
    assert "indian_field_data" in data
    assert data["indian_field_data"]["status"] in ["REAL INDIAN FIELD DATA NOT LOADED", "LOADED"]


def test_leakage_protection():
    """Verify that train, val, and held-out test splits have zero survey or site overlap."""
    assert check_leakage(), "Dataset leakage check must pass with zero survey/site overlap"


def test_metrics_source_separation():
    """Verify metrics are strictly separated into real, hybrid, sim, and summary files."""
    root_dir = Path(__file__).resolve().parent.parent
    metrics_dir = root_dir / "artifacts" / "metrics"

    real_f = metrics_dir / "real_metrics.json"
    hybrid_f = metrics_dir / "hybrid_metrics.json"
    sim_f = metrics_dir / "sim_metrics.json"
    summary_f = metrics_dir / "summary_metrics.json"

    assert real_f.exists(), "real_metrics.json must exist"
    assert hybrid_f.exists(), "hybrid_metrics.json must exist"
    assert sim_f.exists(), "sim_metrics.json must exist"
    assert summary_f.exists(), "summary_metrics.json must exist"

    real_data = json.loads(real_f.read_text(encoding="utf-8"))
    assert real_data["source_type"] == "real"
    # Ghost net in real metrics must be NOT_ESTABLISHED
    assert real_data["classes"]["ghost_net"]["status"] == "NOT_ESTABLISHED"
    assert "pending verified field data" in real_data["classes"]["ghost_net"]["disclaimer"]
    # Wreck and trap real metrics exist
    assert "wreck_debris" in real_data["classes"]
    assert "trap_pot" in real_data["classes"]

    hybrid_data = json.loads(hybrid_f.read_text(encoding="utf-8"))
    assert hybrid_data["source_type"] == "hybrid"
    assert "ghost_net" in hybrid_data["classes"]
    assert hybrid_data["classes"]["ghost_net"]["recall_at_iou50"] >= 0.80

    sim_data = json.loads(sim_f.read_text(encoding="utf-8"))
    assert sim_data["source_type"] == "sim"


def test_api_load_real_survey():
    """Verify loading real survey populates detections with source_type='REAL'."""
    client = TestClient(app)
    payload = {
        "survey_id": "SRV_TEST_REAL",
        "site_name": "Test Real Shelf Survey",
        "source_file": "test_real.xtf"
    }
    response = client.post("/api/surveys/load_real", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "LOADED_REAL_SURVEY"
    assert data["source_type"] == "REAL"

    # Check targets returned for this survey
    targets_resp = client.get(f"/api/targets?survey_id=SRV_TEST_REAL")
    assert targets_resp.status_code == 200
    targets_data = targets_resp.json()
    assert targets_data["count"] >= 1
    assert targets_data["targets"][0]["source_type"] == "REAL"


def test_api_target_inspection_layers():
    """Verify Target Inspector layers endpoint returns all 8 aligned inspection layers."""
    client = TestClient(app)
    # Get any available target ID
    targets_resp = client.get("/api/targets")
    assert targets_resp.status_code == 200
    targets = targets_resp.json()["targets"]
    assert len(targets) > 0

    tid = targets[0]["target_id"]
    layers_resp = client.get(f"/api/targets/{tid}/layers")
    assert layers_resp.status_code == 200
    data = layers_resp.json()

    assert data["target_id"] == tid
    assert "source_type" in data
    assert data["alignment_verified"] is True
    assert len(data["layers_available"]) == 8
    assert "raw_intensity" in data["layers_available"]
    assert "sato_ridge" in data["layers_available"]
    assert "net_signature_points" in data["layers_available"]
    assert "physics_ray_trace" in data["layers_available"]


def test_report_export_provenance():
    """Verify reports include source_type in JSON, CSV, and GeoJSON."""
    sample_targets = [
        {
            "target_id": "TGT_REAL_01",
            "source_type": "REAL",
            "class_name": "wreck_debris",
            "status": "CONFIRMED_HAZARD",
            "priority": 0.92,
            "hazard_confidence": 94.0,
            "lat": 13.085,
            "lon": 80.298,
            "utm_easting": 423950.0,
            "utm_northing": 1446800.0,
            "zone": 44,
            "r95_m": 2.1,
            "position_status": "AVAILABLE",
            "length_m": 12.0,
            "width_m": 2.4,
            "height_m": 2.6,
            "height_status": "AVAILABLE",
            "orientation_deg": 45.0,
            "views": 2,
            "review_status": "CONFIRMED",
        }
    ]

    csv_out = export_csv(sample_targets)
    assert "source_type" in csv_out
    assert "REAL" in csv_out

    json_out = json.loads(export_json(sample_targets))
    assert json_out.get("policy") == "REAL_DATA_FIRST"
    assert json_out["targets"][0]["source_type"] == "REAL"

    geojson_out = json.loads(export_geojson(sample_targets))
    pin_props = geojson_out["features"][0]["properties"]
    assert pin_props["source_type"] == "REAL"
