"""
Test Milestone 10: Operations Dashboard, Demo Presentation Script & Final Evaluation Metrics.
Validates:
  - Frontend static assets (index.html, style.css, app.js)
  - FastAPI dashboard mounting
  - DEMO_SCRIPT.md content & all 6 scenarios
  - Final evaluation metrics artifact (targets vs measured)
  - Architectural ablation study artifact
  - Core system documentation suite
"""

import json
from pathlib import Path
from fastapi.testclient import TestClient
from backend.sagarnetra.api.app import app


def test_frontend_assets_exist():
    """Verify that all core dashboard frontend assets are present and valid."""
    root_dir = Path(__file__).resolve().parent.parent
    frontend_dir = root_dir / "frontend"

    assert frontend_dir.exists(), "frontend/ directory must exist"

    index_html = frontend_dir / "index.html"
    assert index_html.exists(), "frontend/index.html must exist"
    content_html = index_html.read_text(encoding="utf-8")
    assert "SagarNetra" in content_html
    assert "waterfallCanvas" in content_html
    assert "coverageCanvas" in content_html
    assert "swipeContainer" in content_html or "swipe-container" in content_html
    assert "labCanvas" in content_html or "labPodCanvas" in content_html

    style_css = frontend_dir / "style.css"
    assert style_css.exists(), "frontend/style.css must exist"
    content_css = style_css.read_text(encoding="utf-8")
    assert "#071426" in content_css or "#0B2545" in content_css or "#00D4B2" in content_css

    app_js = frontend_dir / "app.js"
    assert app_js.exists(), "frontend/app.js must exist"
    content_js = app_js.read_text(encoding="utf-8")
    assert "initWebSocket" in content_js or "WebSocket" in content_js
    assert "renderTargetCropCanvas" in content_js
    assert "renderLabWaterfall" in content_js or "renderLabCanvases" in content_js


def test_fastapi_serves_dashboard():
    """Verify that FastAPI serves index.html at root."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "SagarNetra" in response.text


def test_demo_script_scenarios():
    """Verify DEMO_SCRIPT.md contains all 6 required judge walkthrough scenarios and differentiators."""
    root_dir = Path(__file__).resolve().parent.parent
    demo_script_path = root_dir / "docs" / "DEMO_SCRIPT.md"

    assert demo_script_path.exists(), "docs/DEMO_SCRIPT.md must exist"
    content = demo_script_path.read_text(encoding="utf-8")

    # Verify all 6 demo scenes
    assert "Chennai Port" in content, "Scenario A: Chennai Port must be present"
    assert "Gulf of Mannar" in content, "Scenario B: Gulf of Mannar must be present"
    assert "Kochi" in content, "Scenario C: Kochi Channel must be present"
    assert "Acoustic Interference" in content or "Interference" in content, "Scenario D: Interference must be present"
    assert "Visakhapatnam" in content, "Scenario E: Visakhapatnam post-cyclone must be present"
    assert "SonarForge Lab" in content, "Scenario F: SonarForge Lab must be present"

    # Verify differentiators table
    assert "Net Signature Head" in content
    assert "Physics Verifier" in content
    assert "Honest Error Budget" in content or "r95" in content or "r_{95}" in content
    assert "Disaster Response" in content or "Post-Disaster" in content


def test_final_evaluation_metrics_artifact():
    """Verify final evaluation metrics artifact structure and target achievements."""
    root_dir = Path(__file__).resolve().parent.parent
    metrics_path = root_dir / "artifacts" / "metrics" / "final_evaluation_metrics.json"

    assert metrics_path.exists(), "final_evaluation_metrics.json must exist"
    data = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert data.get("system") == "SagarNetra"
    assert "targets_vs_measured" in data
    assert len(data["targets_vs_measured"]) >= 5

    # Check key targets
    targets_map = {item["metric"]: item["status"] for item in data["targets_vs_measured"]}
    assert "Ghost Net Recall @ <= 2 FA/km²" in targets_map
    assert targets_map["Ghost Net Recall @ <= 2 FA/km²"] == "ACHIEVED"
    assert "Expected Calibration Error (ECE)" in targets_map
    assert targets_map["Expected Calibration Error (ECE)"] == "ACHIEVED"
    assert "Geotagging Error CEP95" in targets_map
    assert targets_map["Geotagging Error CEP95"] == "ACHIEVED"

    # Check class performance
    assert "class_performance" in data
    assert "ghost_net" in data["class_performance"]
    assert data["class_performance"]["ghost_net"]["recall_at_iou50"] >= 0.80

    # Check calibration numbers
    assert "calibration_analysis" in data
    assert data["calibration_analysis"]["calibrated_ece"] <= 0.05


def test_ablation_study_artifact():
    """Verify ablation study progression from A0 to A5."""
    root_dir = Path(__file__).resolve().parent.parent
    ablation_path = root_dir / "artifacts" / "metrics" / "ablation_study.json"

    assert ablation_path.exists(), "ablation_study.json must exist"
    data = json.loads(ablation_path.read_text(encoding="utf-8"))

    assert "stages" in data
    assert len(data["stages"]) == 6  # A0 through A5

    # Ensure recall increases as specialized modules are added
    recalls = [s["ghost_net_recall"] for s in data["stages"]]
    assert recalls[-1] > recalls[0], "Full pipeline recall must exceed baseline YOLO"

    # Ensure false alarms per km2 decrease with physics verification
    fa_baseline = data["stages"][0]["false_alarms_per_km2"]
    fa_physics = data["stages"][3]["false_alarms_per_km2"]
    assert fa_physics < fa_baseline, "Physics verification must reduce false alarms"


def test_documentation_suite_integrity():
    """Verify that ARCHITECTURE.md, MODEL_CARD.md, API.md, and DATASET_CARD.md exist and are non-empty."""
    root_dir = Path(__file__).resolve().parent.parent

    docs = [
        root_dir / "docs" / "ARCHITECTURE.md",
        root_dir / "docs" / "MODEL_CARD.md",
        root_dir / "docs" / "API.md",
        root_dir / "docs" / "DEMO_SCRIPT.md",
        root_dir / "DATASET_CARD.md"
    ]

    for doc_path in docs:
        assert doc_path.exists(), f"Document {doc_path} must exist"
        assert len(doc_path.read_text(encoding="utf-8").strip()) > 200, f"Document {doc_path} must be substantial"
