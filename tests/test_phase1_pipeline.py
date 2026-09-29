"""
tests/test_phase1_pipeline.py
=============================
Automated test suite for Phase 1: Standalone SagarNetra SSS Detection Pipeline.
Validates:
1. SSS vs Optical modality classification
2. Full standalone pipeline execution without UI / YOLO
3. Strict honesty: no fake coordinates or dimensions for image-only input
4. Real georeferencing and physical dimensions when navigation CSV is provided
5. Automatic rejection and invalid_input handling for optical photos
6. Physics suppression of natural seabed textures
7. Strict Pydantic schema validation of output JSON reports
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image

from backend.sagarnetra.preprocess.modality import check_image_modality, ModalityCheckResult
from backend.sagarnetra.io.pipeline_schema import PipelineReport
from scripts.run_pipeline import run_pipeline

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "tests" / "fixtures"


def test_modality_check_monochrome_sss():
    img_gray = np.full((128, 128), 120, dtype=np.uint8)
    res = check_image_modality(img_gray)
    assert res.is_sss is True
    assert res.detected_modality == "SIDE_SCAN_SONAR"
    assert res.chromatic_dispersion == 0.0


def test_modality_check_optical_photo():
    # Daylight optical photo with strong blue/green dominance and low red
    opt = np.zeros((128, 128, 3), dtype=np.uint8)
    opt[:, :, 0] = 20   # Red
    opt[:, :, 1] = 130  # Green
    opt[:, :, 2] = 220  # Blue
    res = check_image_modality(opt)
    assert res.is_sss is False
    assert res.detected_modality == "OPTICAL_RGB_PHOTO"
    assert res.chromatic_dispersion > 16.0


def test_pipeline_image_only_no_fake_coordinates(tmp_path: Path):
    """
    Test Phase 1 requirement:
    - Image-only input: geo.status == UNAVAILABLE, lat/lon null, height null, dims metres null.
    """
    img_path = FIXTURES_DIR / "real_sss_tile_wreck.png"
    assert img_path.exists(), f"Missing fixture {img_path}"

    report, _ar, json_p, overlay_p = run_pipeline(
        image_path=img_path,
        nav_path=None,
        out_dir=tmp_path,
    )

    assert report.status == "SUCCESS"
    assert report.modality.is_sss is True
    assert report.detection_count > 0
    assert json_p.exists()
    assert overlay_p.exists()

    # Re-validate with Pydantic from raw disk file
    with open(json_p, "r", encoding="utf-8") as f:
        loaded = PipelineReport.model_validate(json.load(f))

    for d in loaded.detections:
        assert d.geo.status == "UNAVAILABLE"
        assert d.geo.lat is None
        assert d.geo.lon is None
        assert d.geo.utm is None
        assert d.height_m is None
        assert d.dims.length_m is None
        assert d.dims.width_m is None
        assert d.raw_candidate_source == "OS_CFAR"


def test_pipeline_with_navigation_georeferencing(tmp_path: Path):
    """
    Test Phase 1 requirement:
    - With nav CSV: geo.status == AVAILABLE, valid WGS84 lat/lon and UTM coordinates.
    """
    img_path = FIXTURES_DIR / "real_sss_tile_wreck.png"
    nav_path = FIXTURES_DIR / "survey_nav_sample.csv"
    assert img_path.exists()
    assert nav_path.exists()

    report, _ar, json_p, overlay_p = run_pipeline(
        image_path=img_path,
        nav_path=nav_path,
        out_dir=tmp_path,
    )

    assert report.status == "SUCCESS"
    assert report.detection_count > 0

    with open(json_p, "r", encoding="utf-8") as f:
        loaded = PipelineReport.model_validate(json.load(f))

    d0 = loaded.detections[0]
    assert d0.geo.status == "AVAILABLE"
    assert d0.geo.lat is not None and 12.0 < d0.geo.lat < 14.0
    assert d0.geo.lon is not None and 80.0 < d0.geo.lon < 81.0
    assert d0.geo.utm is not None
    assert d0.dims.length_m is not None and d0.dims.length_m > 0
    assert d0.dims.width_m is not None and d0.dims.width_m > 0


def test_pipeline_rejects_optical_photo(tmp_path: Path):
    """
    Test Phase 1 requirement:
    - Optical photo input: returns invalid_input, 0 detections, rejection overlay.
    """
    img_path = FIXTURES_DIR / "optical_rgb_photo.jpg"
    assert img_path.exists()

    report, _ar, json_p, overlay_p = run_pipeline(
        image_path=img_path,
        nav_path=None,
        out_dir=tmp_path,
    )

    assert report.status == "INVALID_INPUT"
    assert report.modality.is_sss is False
    assert report.modality.detected_modality == "OPTICAL_RGB_PHOTO"
    assert report.detection_count == 0
    assert len(report.detections) == 0
    assert json_p.exists()
    assert overlay_p.exists()


def test_pipeline_suppresses_natural_seabed(tmp_path: Path):
    """
    Test Phase 1 requirement:
    - Natural seabed ripples: suppressed by physics layer into natural_suppressed.
    """
    img_path = FIXTURES_DIR / "natural_seabed_negative.png"
    assert img_path.exists()

    report, _ar, json_p, overlay_p = run_pipeline(
        image_path=img_path,
        nav_path=None,
        out_dir=tmp_path,
    )

    assert report.status == "SUCCESS"
    assert report.modality.is_sss is True
    for d in report.detections:
        assert d.decision == "natural_suppressed"
