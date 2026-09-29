"""
tests/test_no_fake_coordinates.py
=================================
Verifies that SagarNetra strictly refuses to invent fake coordinates, fake r95,
or fake physical dimensions when analyzing uncalibrated or image-only inputs
without genuine navigation metadata.
"""

import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend.sagarnetra.api.app import app


def test_random_image_upload_no_fake_coordinates():
    """
    Uploading a random sonar image (PNG/JPG) without navigation metadata MUST:
    - Operate in IMAGE_ONLY mode
    - Output position_status = 'UNAVAILABLE'
    - Output lat = None, lon = None, r95_m = None
    - Output dimensions_status = 'UNAVAILABLE' (no verified ground/pixel scale)
    - Refuse to manufacture any coordinates
    """
    client = TestClient(app)

    # Use real unreferenced sonar crop fixture
    with open("tests/fixtures/wreck_real.png", "rb") as f:
        buf = io.BytesIO(f.read())

    response = client.post(
        "/api/upload",
        files={"file": ("random_sonar_crop.png", buf, "image/png")},
        data={"survey_id": "SRV_UNREFERENCED_01", "site_name": "Unknown_Seabed"}
    )

    assert response.status_code == 200, f"Upload failed: {response.text}"
    data = response.json()

    # 1. Mode check
    assert data["mode"] == "IMAGE_ONLY"
    assert data["input"]["navigation_present"] is False

    # 2. Honest coordinates verification
    target = data["targets"][0]
    pos = target["position"]
    assert pos["position_status"] == "UNAVAILABLE"
    assert "No navigation metadata was supplied" in pos["position_reason"]
    assert pos["lat"] is None
    assert pos["lon"] is None
    assert pos["r95_m"] is None

    # 3. Honest dimensions verification
    dims = target["dimensions"]
    assert dims["dimensions_status"] == "UNAVAILABLE"
    assert "No verified ground/pixel scale" in dims["dimensions_reason"]
    assert dims["length_m"] is None
    assert dims["width_m"] is None
    assert dims["height_m"] is None

    # 4. Check DB persistence consistency
    targets_resp = client.get("/api/targets?survey_id=SRV_UNREFERENCED_01")
    assert targets_resp.status_code == 200
    persisted_target = targets_resp.json()["targets"][0]
    assert persisted_target["position_status"] == "UNAVAILABLE"
    assert persisted_target["lat"] is None
    assert persisted_target["r95_m"] is None
    assert persisted_target["height_status"] == "UNAVAILABLE"
