"""
tests/test_echosift.py
======================
Unit & integration tests for EchoSift Physics-Verified Sonar Detection Layer:
1. Shadow-Highlight Consistency (SHC) formula h = (L_s * H) / (R + L_s) & nadir direction
2. Geometric Regularity Index (GRI) & sand-ripple distinction
3. Motion-artifact mask overlap penalty (>40% suppression)
4. Multi-pass persistence spatial join (<= 5m)
5. Calibrated 5-term logistic fusion formula
6. API routes: /api/echosift/detections, /api/echosift/mode, /api/echosift/feedback, /api/echosift/export/*
"""
import pytest
import numpy as np
from fastapi.testclient import TestClient

from backend.sagarnetra.verify.echosift import EchoSiftPipeline, EchoSiftEvidence
from backend.sagarnetra.api.app import app

client = TestClient(app)


def test_shc_height_formula_and_nadir_direction():
    """Verify SHC calculates physical height and rejects anti-causal shadows pointing to nadir."""
    # Test 1: Legitimate starboard detection with shadow pointing down-range (offset > 0)
    # Slant range R = 25m, altitude H = 8m, shadow length L_s = 4.5m
    # h = (4.5 * 8) / (25 + 4.5) = 36 / 29.5 = 1.22m
    shc_score, h_m, shadow_side, reason = EchoSiftPipeline.compute_shc(
        slant_range_m=25.0,
        towfish_alt_m=8.0,
        shadow_len_m=4.5,
        channel="starboard",
        shadow_offset_px=15.0,
        class_name="ghost_net"
    )
    assert shadow_side == "correct"
    assert reason is None
    assert pytest.approx(h_m, 0.05) == 1.22
    assert shc_score > 0.85

    # Test 2: Flat feature with zero shadow length -> flat sediment patch
    shc_score_flat, h_flat, _, flat_reason = EchoSiftPipeline.compute_shc(
        slant_range_m=25.0,
        towfish_alt_m=8.0,
        shadow_len_m=0.1,
        channel="starboard",
        shadow_offset_px=1.0,
        class_name="ghost_net"
    )
    assert h_flat < 0.05
    assert "flat sediment patch" in flat_reason
    assert shc_score_flat <= 0.15

    # Test 3: Anti-causal shadow pointing toward nadir on starboard (offset < 0)
    shc_score_anti, _, shadow_side_anti, anti_reason = EchoSiftPipeline.compute_shc(
        slant_range_m=25.0,
        towfish_alt_m=8.0,
        shadow_len_m=3.0,
        channel="starboard",
        shadow_offset_px=-5.0,
        class_name="ghost_net"
    )
    assert shadow_side_anti == "incorrect"
    assert "Anti-causal shadow" in anti_reason
    assert shc_score_anti < 0.10


def test_geometric_regularity_and_sand_ripples():
    """Verify GRI distinguishes localized fishing net mesh from widespread periodic sand ripples."""
    pipeline = EchoSiftPipeline()

    # Synthetic periodic patch (net mesh / parallel ribbing)
    y, x = np.mgrid[:64, :64]
    patch_periodic = (np.sin(x * 0.4) * 127 + 128).astype(np.uint8)

    # Surrounding 3x ring with uniform random speckle (localized target -> net)
    ring_random = np.random.randint(50, 150, (192, 192), dtype=np.uint8)
    reg_net, is_ripple_net = pipeline.compute_regularity_index(patch_periodic, ring_random)
    assert not is_ripple_net
    assert reg_net > 0.50

    # Surrounding 3x ring with SAME periodicity (sand dunes extending across seabed)
    ring_periodic = (np.sin(x * 0.4) * 127 + 128).astype(np.uint8)
    # Tile it across 192x192
    ring_periodic_full = np.tile(ring_periodic, (3, 3))
    reg_ripple, is_ripple_dune = pipeline.compute_regularity_index(patch_periodic, ring_periodic_full)
    assert is_ripple_dune is True
    assert reg_ripple <= 0.25


def test_motion_mask_veto():
    """Verify that detections with >40% overlap with corrupted motion pings are penalized/vetoed."""
    pipeline = EchoSiftPipeline()
    corrupted_pings = list(range(100, 120))  # 20 corrupted pings

    # Case 1: Target spans pings 105 to 115 (100% inside corrupted zone)
    overlap_heavy = pipeline.evaluate_motion_overlap(105, 115, corrupted_pings)
    assert overlap_heavy >= 0.90
    conf, suppressed, reason = pipeline.fuse_evidence(
        cnn_score=0.85,
        shc_score=0.90,
        regularity_score=0.80,
        motion_penalty=overlap_heavy,
        persistence_score=0.50
    )
    assert suppressed is True
    assert "overlap with motion-artifact mask" in reason

    # Case 2: Clean target with 0% overlap
    overlap_clean = pipeline.evaluate_motion_overlap(130, 140, corrupted_pings)
    assert overlap_clean == 0.0


def test_multi_pass_persistence():
    """Verify multi-pass persistence boosts confidence for targets verified across survey lines."""
    pipeline = EchoSiftPipeline()
    target_lat, target_lon = 13.08512, 80.29841
    other_dets = [
        {"lat": 13.08513, "lon": 80.29842, "line_id": "SRV_LINE_08"}  # ~1.5m away
    ]

    score, pass_count, passes = pipeline.evaluate_multi_pass_persistence(
        target_lat, target_lon, "SRV_LINE_07", other_dets, tolerance_m=5.0
    )
    assert pass_count == 2
    assert score == 0.85
    assert "SRV_LINE_08" in passes


def test_echosift_api_endpoints():
    """Verify the EchoSift FastAPI endpoints match docs/API_CONTRACT.md schema."""
    # 1. GET detections with physics verification ON (default)
    res_ver = client.get("/api/echosift/detections?verification=true")
    assert res_ver.status_code == 200
    data_ver = res_ver.json()

    assert data_ver["surveyId"] == "SRV_CHENNAI_LINE_07"
    assert data_ver["suppressionStats"]["totalCnnCandidates"] == 3
    assert data_ver["suppressionStats"]["suppressedFalsePositives"] == 2
    assert data_ver["suppressionStats"]["verifiedHazards"] == 1

    # Ghost net is not suppressed and has high confidence
    ghost_net = next(d for d in data_ver["detections"] if d["id"] == "TGT-001")
    assert ghost_net["class"] == "ghost_net"
    assert ghost_net["confidence"] >= 90.0
    assert ghost_net["suppressed"] is False
    assert ghost_net["heightEstimateM"] == 1.2
    assert ghost_net["shadowSide"] == "correct"

    # Dark sediment patch is suppressed with height 0.0m reason
    sediment = next(d for d in data_ver["detections"] if d["id"] == "TGT-002")
    assert sediment["suppressed"] is True
    assert "height 0.0 m" in sediment["suppressionReason"]

    # Dropout line is suppressed with motion mask reason
    dropout = next(d for d in data_ver["detections"] if d["id"] == "TGT-003")
    assert dropout["suppressed"] is True
    assert "motion mask" in dropout["suppressionReason"]

    # 2. GET detections with physics verification OFF (Raw CNN mode)
    res_raw = client.get("/api/echosift/detections?verification=false")
    assert res_raw.status_code == 200
    data_raw = res_raw.json()
    assert data_raw["suppressionStats"]["suppressedFalsePositives"] == 0
    # In raw mode, all 3 show high confidence CNN proposals
    for det in data_raw["detections"]:
        assert det["suppressed"] is False
        assert det["confidence"] >= 75.0

    # 3. POST /api/echosift/mode to toggle Jetson edge mode
    res_mode = client.post("/api/echosift/mode", json={"mode": "onboard_jetson"})
    assert res_mode.status_code == 200
    assert res_mode.json()["edgeMode"] == "onboard_jetson"

    res_telemetry = client.get("/api/echosift/detections")
    assert res_telemetry.json()["edgeTelemetry"]["tilesPerSec"] == 26.4
    assert res_telemetry.json()["edgeTelemetry"]["latencyMs"] == 14.8

    # Reset mode back to shore
    client.post("/api/echosift/mode", json={"mode": "shore"})

    # 4. POST /api/echosift/feedback
    res_fb = client.post("/api/echosift/feedback", json={"detection_id": "TGT-001", "action": "accept"})
    assert res_fb.status_code == 200
    assert res_fb.json()["action"] == "accept"
    assert res_fb.json()["feedbackTotals"]["accepted"] >= 1

    # 5. GET export in GeoJSON, CSV, JSON, KML
    res_geojson = client.get("/api/echosift/export/geojson")
    assert res_geojson.status_code == 200
    geojson_body = res_geojson.json()
    assert geojson_body["type"] == "FeatureCollection"
    assert len(geojson_body["features"]) == 3

    res_csv = client.get("/api/echosift/export/csv")
    assert res_csv.status_code == 200
    assert "TGT-001" in res_csv.text

    res_kml = client.get("/api/echosift/export/kml")
    assert res_kml.status_code == 200
    assert "<kml" in res_kml.text
