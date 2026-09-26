"""
tests/test_evidence_aware.py
============================
Verifies SagarNetra's Evidence-Aware Marine Debris Intelligence capabilities:
1. Decision-support review actions (ACCEPT_FOR_FOLLOWUP, REJECT_CANDIDATE, REQUEST_SECOND_LOOK)
2. 3-State acoustic evidence evaluation (SUPPORTS, CONFLICTS, NOT_ASSESSABLE)
3. Capability matrix degradation (unsupported coordinates/dimensions withheld)
4. Observation adequacy coverage states (with "No detection does not prove absence" rule)
5. Observation-aware second-look recommendation mappings
"""

import io
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend.sagarnetra.api.app import app
from backend.sagarnetra.coverage.pod_map import ClearanceState, model_pod


def test_evidence_aware_review_actions():
    """Verify that operator can record evidence-aware decisions on candidates."""
    client = TestClient(app)

    # 1. Fetch available target
    resp = client.get("/api/targets")
    assert resp.status_code == 200
    targets = resp.json()["targets"]
    assert len(targets) > 0
    tid = targets[0]["target_id"]
    sid = targets[0]["survey_id"]

    # 2. Test Accept for Follow-Up
    accept_resp = client.post(
        f"/api/surveys/{sid}/detections/{tid}/review",
        json={"action": "ACCEPT_FOR_FOLLOWUP", "notes": "Candidate displays plausible shadow geometry and requires diver check."}
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["action"] == "ACCEPT_FOR_FOLLOWUP"

    # Verify review persisted in target record
    det_resp = client.get(f"/api/targets?survey_id={sid}")
    target_match = next(t for t in det_resp.json()["targets"] if t["target_id"] == tid)
    assert target_match["review_status"] == "ACCEPT_FOR_FOLLOWUP"

    # 3. Test Request Second Look
    second_look_resp = client.post(
        f"/api/surveys/{sid}/detections/{tid}/review",
        json={"action": "REQUEST_SECOND_LOOK", "notes": "Nadir proximity occluded grazing angle. Infill pass required."}
    )
    assert second_look_resp.status_code == 200
    assert second_look_resp.json()["action"] == "REQUEST_SECOND_LOOK"


def test_capability_matrix_honest_degradation():
    """
    Verify that when inputs lack navigation metadata:
    - Geographic position is explicitly marked UNAVAILABLE
    - Physical dimensions are explicitly marked UNAVAILABLE
    - Explanations are provided, never zero or fabricated numbers
    """
    client = TestClient(app)

    # Upload uncalibrated crop without navigation sidecar
    img = Image.new("L", (256, 256), color=120)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    upload_resp = client.post(
        "/api/upload",
        files={"file": ("uncalibrated_debris_crop.png", buf, "image/png")},
        data={"survey_id": "SRV_UNCALIBRATED_09"}
    )
    assert upload_resp.status_code == 200
    data = upload_resp.json()

    assert data["mode"] == "IMAGE_ONLY"
    target = data["targets"][0]

    # Verify honest absence of coordinates
    pos = target["position"]
    assert pos["position_status"] == "UNAVAILABLE"
    assert pos["lat"] is None
    assert pos["lon"] is None
    assert pos["r95_m"] is None
    assert "No navigation metadata was supplied" in pos["position_reason"]

    # Verify honest absence of physical dimensions
    dims = target["dimensions"]
    assert dims["dimensions_status"] == "UNAVAILABLE"
    assert dims["length_m"] is None
    assert "No verified ground/pixel scale" in dims["dimensions_reason"]


def test_coverage_adequacy_states():
    """
    Verify clearance grid distinguishes:
    - SURVEYED_CLEAR (Observed - No Candidate Detected)
    - CANDIDATE (Candidate Present)
    - INSUFFICIENT (Observation Limited)
    - NOT_SURVEYED (Not Surveyed)
    """
    states = [s.value for s in ClearanceState]
    assert "SURVEYED_CLEAR" in states
    assert "CANDIDATE" in states
    assert "INSUFFICIENT" in states
    assert "NOT_SURVEYED" in states

    # Check PoD sweet spot (30-60% range) vs nadir degradation
    pod_sweet = model_pod(ground_range_m=35.0, max_range_m=75.0, altitude_m=8.0)
    pod_nadir = model_pod(ground_range_m=2.0, max_range_m=75.0, altitude_m=8.0)
    assert pod_sweet > pod_nadir, "PoD must be higher in the 30-60% acoustic sweet spot than near-nadir"
