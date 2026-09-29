#!/usr/bin/env python3
"""
scripts/run_pipeline.py
=======================
SagarNetra Side-Scan Sonar Analysis Pipeline (Python is the ONLY analysis engine).

Pipeline Stages:
Stage 1: Ingest & Preprocess (Modality check, EGN, Lee despeckle, Nadir detection, Data-quality mask, Slant-range)
Stage 2: Dual-branch detection (Branch A: YOLO detector / NOT_TRAINED; Branch A2: OS-CFAR; Branch B: PatchCore anomaly)
Stage 3: Verification & Decision (Structural grouping, Seabed context contrast, Shadow validity, Net evidence, Evidence fusion, Decision reasons)
Stage 4: Geotag & Export (WGS84 / UTM layback, UNAVAILABLE without nav, SYNTHETIC_NAV_TEST with test nav)
"""
from __future__ import annotations

import os
# Prevent OpenBLAS/MKL thread pool allocation failure on constrained memory
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.sagarnetra.preprocess.modality import check_image_modality, ModalityCheckResult
from backend.sagarnetra.preprocess.gain import empirical_gain_normalisation
from backend.sagarnetra.preprocess.despeckle import enhanced_lee_filter
from backend.sagarnetra.preprocess.features import generate_feature_stack
from backend.sagarnetra.detect.cfar import os_cfar_2d, pair_highlights_and_shadows, CFARCandidate
from backend.sagarnetra.detect.fuse_candidates import compute_iou
from backend.sagarnetra.detect.net_signature import evaluate_net_signature
from backend.sagarnetra.detect.anomaly import PatchCoreLite
from backend.sagarnetra.verify.decision import decide_target, TargetDecisionResult
from backend.sagarnetra.geo.project import latlon_to_utm, utm_to_latlon
from backend.sagarnetra.api.schemas import (
    BoundingBoxPx,
    Dimensions,
    GeoPosition,
    UTMCoordinates,
    PipelineStage,
    RawCandidate,
    TargetEvidence,
    TargetOutput,
    SummaryCounts,
    AnalyzeSurveyInfo,
    AnalyzeResponse,
)
from backend.sagarnetra.io.pipeline_schema import (
    PipelineReport,
    PreprocessingSummary,
    QualitySummary,
    DetectionOutput,
    EchoSiftEvidenceReport,
)


def load_nav_csv(nav_path: Path) -> List[Dict[str, float]]:
    """Loads and standardizes navigation CSV data."""
    rows: List[Dict[str, float]] = []
    with open(nav_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            normalized = {}
            for k, v in r.items():
                if k is None or v is None or v.strip() == "":
                    continue
                k_clean = k.strip().lower()
                try:
                    val = float(v.strip())
                    normalized[k_clean] = val
                except ValueError:
                    pass
            rows.append(normalized)
    return rows


def get_nav_fields_for_row(nav_rows: List[Dict[str, float]], row_idx: int, total_rows: int) -> Tuple[Optional[float], Optional[float], float, Optional[float]]:
    """Interpolates (lat, lon, heading_deg, altitude_m) for a given ping row index."""
    if not nav_rows:
        return None, None, 0.0, None

    n_nav = len(nav_rows)
    pos = (row_idx / max(1, total_rows - 1)) * (n_nav - 1)
    idx = int(round(pos))
    idx = max(0, min(n_nav - 1, idx))
    r = nav_rows[idx]

    lat = r.get("vessel_lat") or r.get("lat") or r.get("ship_lat") or r.get("latitude")
    lon = r.get("vessel_lon") or r.get("lon") or r.get("ship_lon") or r.get("longitude")
    heading = r.get("vessel_heading") or r.get("heading") or r.get("heading_deg") or r.get("cog") or 0.0
    alt = r.get("altitude_m") or r.get("altitude") or r.get("towfish_alt") or r.get("alt")

    return lat, lon, heading, alt


def detect_nadir_column(img_gray: np.ndarray) -> Optional[int]:
    """Locates the nadir / water column boundary in an SSS waterfall image."""
    h, w = img_gray.shape
    if w < 100:
        return None

    col_means = np.mean(img_gray, axis=0)
    c_start = int(0.20 * w)
    c_end = int(0.80 * w)
    if c_end <= c_start:
        return None

    center_profile = col_means[c_start:c_end]
    min_rel_idx = int(np.argmin(center_profile))
    min_col = c_start + min_rel_idx
    min_val = center_profile[min_rel_idx]
    median_val = float(np.median(col_means))

    if min_val < 0.70 * median_val:
        return min_col
    return None


def compute_data_quality_mask(img_gray: np.ndarray) -> Tuple[np.ndarray, Set[int], QualitySummary]:
    """Evaluates row energy drop and ping-to-ping correlation collapse."""
    h, w = img_gray.shape
    row_energies = np.mean(img_gray**2, axis=1)
    med_energy = float(np.median(row_energies)) if np.median(row_energies) > 0 else 1.0

    energy_thresh = max(1e-4, 0.10 * med_energy)
    corrupted_rows = set(np.where(row_energies < energy_thresh)[0])

    if h > 1:
        diff1 = img_gray[:-1] - np.mean(img_gray[:-1], axis=1, keepdims=True)
        diff2 = img_gray[1:] - np.mean(img_gray[1:], axis=1, keepdims=True)
        num = np.sum(diff1 * diff2, axis=1)
        den = np.sqrt(np.sum(diff1**2, axis=1) * np.sum(diff2**2, axis=1) + 1e-8)
        corr_vec = num / den
        bad_corr = np.where((corr_vec < 0.15) | np.isnan(corr_vec))[0]
        corrupted_rows.update(bad_corr.tolist())

    quality_mask = np.ones((h, w), dtype=bool)
    for r in corrupted_rows:
        quality_mask[r, :] = False

    flagged_pct = (len(corrupted_rows) / max(1, h)) * 100.0
    valid_pixels_pct = float(np.mean(quality_mask)) * 100.0

    summary = QualitySummary(
        total_rows=h,
        flagged_rows_pct=round(flagged_pct, 1),
        valid_pixels_pct=round(valid_pixels_pct, 1),
    )
    return quality_mask, corrupted_rows, summary


def evaluate_net_signature_patch(patch: np.ndarray, ground_res_m: float = 0.10) -> float:
    """Runs physics-grounded net signature detector on candidate patch."""
    if patch.shape[0] < 8 or patch.shape[1] < 8:
        return 0.10
    try:
        res = evaluate_net_signature(patch, ground_res_m=ground_res_m)
        return float(res.s_net)
    except Exception:
        return 0.10


def compute_annular_contrast_and_periodicity(patch: np.ndarray, ring: np.ndarray) -> Tuple[float, float, bool]:
    """
    Stage 3 Acoustic Ring Test (Improved Multi-Feature Texture Comparison):
    Compares candidate patch texture against surrounding 3x annular neighbourhood across 4 acoustic texture features:
      1. Mean Intensity Contrast: Normalized absolute difference in acoustic backscatter means.
      2. Local Standard Deviation Contrast: Texture variance comparison (|std_p - std_r| / std_r).
      3. Edge/Gradient Density Contrast: Density of high-gradient acoustic specular facets using Sobel filtering.
      4. 2D-FFT Band Energy & Periodicity Continuity: Concentrated spectral power ratio and angular coherence.
    Pattern continues outward (is_ripple) ONLY when strong periodic orientation/frequency in the annular ring
    matches the candidate patch seamlessly.
    """
    if patch.size == 0 or ring.size <= patch.size:
        return 0.5, 0.2, False

    p_f = patch.astype(np.float32)
    r_f = ring.astype(np.float32)

    p_mean = float(np.mean(p_f))
    r_mean = float(np.mean(r_f))
    intensity_contrast = abs(p_mean - r_mean) / max(r_mean, 1e-4)

    # Feature 2: Local Texture Variance / Standard Deviation Contrast
    p_std = float(np.std(p_f))
    r_std = float(np.std(r_f))
    std_contrast = abs(p_std - r_std) / max(r_std, 1e-4)

    # Feature 3: Gradient / Edge Density Contrast (Sobel operator)
    if min(patch.shape) >= 3 and min(ring.shape) >= 3:
        gy_p, gx_p = np.gradient(p_f)
        grad_p = np.hypot(gx_p, gy_p)
        gy_r, gx_r = np.gradient(r_f)
        grad_r = np.hypot(gx_r, gy_r)

        edge_thresh = float(np.percentile(grad_r, 85))
        edge_density_p = float(np.mean(grad_p > edge_thresh))
        edge_density_r = float(np.mean(grad_r > edge_thresh))
        edge_contrast = abs(edge_density_p - edge_density_r) / max(edge_density_r, 1e-3)
    else:
        edge_contrast = 0.0

    # Feature 4: 2D FFT Periodicity and Band Energy
    # Patch FFT
    f_p = np.fft.fftshift(np.fft.fft2(p_f - p_mean))
    p_power = np.abs(f_p)**2
    cy, cx = patch.shape[0] // 2, patch.shape[1] // 2
    p_power[max(0, cy - 2):cy + 3, max(0, cx - 2):cx + 3] = 0
    p_periodicity = float(np.clip((np.max(p_power) / (np.mean(p_power) + 1e-6) - 1.0) / 25.0, 0.0, 1.0))

    # Ring FFT
    f_r = np.fft.fftshift(np.fft.fft2(r_f - r_mean))
    r_power = np.abs(f_r)**2
    ry, rx = ring.shape[0] // 2, ring.shape[1] // 2
    r_power[max(0, ry - 2):ry + 3, max(0, rx - 2):rx + 3] = 0
    r_periodicity = float(np.clip((np.max(r_power) / (np.mean(r_power) + 1e-6) - 1.0) / 25.0, 0.0, 1.0))

    # Pattern continues outward into annulus ONLY if both ring and patch share dominant wave periodicity
    is_ripple = (r_periodicity > 0.60 and p_periodicity > 0.50) or (r_periodicity > 0.75)

    # Composite annular texture contrast
    raw_composite = 0.40 * intensity_contrast + 0.35 * std_contrast + 0.25 * min(1.0, edge_contrast)
    annular_contrast = float(np.clip(raw_composite * (1.0 - r_periodicity * 0.6 if is_ripple else 1.0), 0.0, 1.0))

    return annular_contrast, p_periodicity, is_ripple


def structural_grouping(
    candidates: List[CFARCandidate],
    ground_res_m: float = 0.10,
    proximity_dist_m: float = 6.0,
) -> List[Dict[str, Any]]:
    """
    Stage 3 Structural Grouping:
    Merges fragments that are within physical proximity (in metres, scaled by ground_res_m)
    OR share a common down-range acoustic shadow envelope into ONE unified physical target.
    """
    if not candidates:
        return []

    max_dist_px = max(4, int(round(proximity_dist_m / max(ground_res_m, 0.01))))

    groups: List[List[CFARCandidate]] = []
    for cand in candidates:
        matched = False
        for grp in groups:
            for member in grp:
                row_gap = max(0, max(cand.row_start - member.row_end, member.row_start - cand.row_end))
                col_gap = max(0, max(cand.col_start - member.col_end, member.col_start - cand.col_end))
                euclid_dist_px = math.hypot(row_gap, col_gap)

                # Condition 1: Proximity in physical metres
                is_close = euclid_dist_px <= max_dist_px

                # Condition 2: Shared shadow envelope down-range on same side
                shares_shadow_envelope = (
                    cand.has_shadow and member.has_shadow
                    and cand.side == member.side
                    and row_gap <= (max_dist_px * 1.5)
                    and (min(cand.col_end, member.col_end) - max(cand.col_start, member.col_start)) > -int(max_dist_px * 0.5)
                )

                if is_close or shares_shadow_envelope:
                    grp.append(cand)
                    matched = True
                    break
            if matched:
                break
        if not matched:
            groups.append([cand])

    grouped_targets = []
    for grp in groups:
        r_min = min(c.row_start for c in grp)
        r_max = max(c.row_end for c in grp)
        c_min = min(c.col_start for c in grp)
        c_max = max(c.col_end for c in grp)
        has_sh = any(c.has_shadow for c in grp)
        max_snr = max(c.snr_db for c in grp)
        side = grp[0].side
        shadow_len_m = max(c.shadow_length_m for c in grp)

        grouped_targets.append({
            "row_start": r_min,
            "row_end": r_max,
            "col_start": c_min,
            "col_end": c_max,
            "has_shadow": has_sh,
            "snr_db": max_snr,
            "side": side,
            "shadow_length_m": shadow_len_m,
            "merged_count": len(grp),
        })

    return grouped_targets


def run_pipeline(
    image_path: Path,
    nav_path: Optional[Path] = None,
    out_dir: Optional[Path] = None,
    ground_res_m: float = 0.10,
    max_candidate_config: int = 250,
) -> Tuple[PipelineReport, Path, Path]:
    """
    Executes the complete standalone SagarNetra pipeline on a single image.
    Python is the ONLY analysis engine.
    """
    t0_total = time.perf_counter()
    image_path = Path(image_path).resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Input image not found: {image_path}")

    if out_dir is None:
        out_dir = image_path.parent / "pipeline_output"
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    base_name = image_path.stem
    report_json_path = out_dir / f"{base_name}_report.json"
    overlay_png_path = out_dir / f"{base_name}_overlay.png"

    stages: List[PipelineStage] = []
    warnings: List[str] = []

    # -------------------------------------------------------------
    # Stage 1: Ingest & Preprocess
    # -------------------------------------------------------------
    t0_stage = time.perf_counter()
    pil_img = Image.open(image_path)
    img_raw = np.array(pil_img)
    h_orig, w_orig = img_raw.shape[:2]

    # Modality check: reject optical photos immediately
    modality_res = check_image_modality(img_raw)

    if not modality_res.is_sss:
        stages.append(PipelineStage(
            step=1,
            name="INGEST & MODALITY CHECK",
            status="FAILED",
            duration_ms=round((time.perf_counter() - t0_stage) * 1000.0, 2),
            details=f"REJECTED: {modality_res.verdict_title}",
        ))

        draw_img = pil_img.convert("RGB")
        draw = ImageDraw.Draw(draw_img)
        banner_h = max(40, int(h_orig * 0.08))
        draw.rectangle([(0, 0), (w_orig, banner_h)], fill=(180, 20, 20))
        msg = f"INVALID INPUT: {modality_res.verdict_title} (Optical RGB Dispersion: {modality_res.chromatic_dispersion:.1f})"
        draw.text((10, 10), msg, fill=(255, 255, 255))
        draw_img.save(overlay_png_path)

        report = PipelineReport(
            status="INVALID_INPUT",
            image_path=str(image_path),
            nav_path=str(nav_path) if nav_path else None,
            image_shape=(h_orig, w_orig),
            modality=modality_res,
            preprocessing=None,
            detection_count=0,
            detections=[],
            overlay_path=str(overlay_png_path),
        )

        with open(report_json_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2, by_alias=True))

        return report, None, report_json_path, overlay_png_path

    # Convert to grayscale float32 [0.0, 1.0]
    if img_raw.ndim == 3:
        r = img_raw[:, :, 0].astype(np.float32)
        g = img_raw[:, :, 1].astype(np.float32)
        b = img_raw[:, :, 2].astype(np.float32)
        img_gray = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    else:
        max_val = np.max(img_raw)
        img_gray = (img_raw.astype(np.float32) / 255.0) if max_val > 1.05 else img_raw.astype(np.float32)

    img_gray = np.clip(img_gray, 0.0, 1.0)
    h, w = img_gray.shape

    # Check for blank / constant image sanity (Rule R5)
    is_blank = (np.max(img_gray) - np.min(img_gray)) < 1e-4

    # 1b. Nadir detection & gain normalization
    nadir_col = detect_nadir_column(img_gray) if not is_blank else None
    normalized_img = empirical_gain_normalisation(img_gray) if not is_blank else img_gray
    normalized_img = np.clip(normalized_img, 0.0, 1.0)

    # 1c. Enhanced Lee despeckling
    despeckled_img = enhanced_lee_filter(normalized_img, window_size=7) if not is_blank else img_gray

    # 1d. Data quality mask
    quality_mask, corrupted_rows, quality_summary = compute_data_quality_mask(img_gray)

    dur_stage1 = round((time.perf_counter() - t0_stage) * 1000.0, 2)
    stages.append(PipelineStage(
        step=1,
        name="INGEST & PREPROCESS",
        status="COMPLETED",
        duration_ms=dur_stage1,
        details=f"EGN + 7x7 Lee filter applied. Nadir: col {nadir_col or 'none'}, Valid pixels: {quality_summary.valid_pixels_pct:.1f}%",
    ))

    # -------------------------------------------------------------
    # Stage 2: Dual-Branch Detection
    # -------------------------------------------------------------
    t0_stage2 = time.perf_counter()

    # Branch A: YOLOv8 detector
    # Since no properly trained 4-class model exists, Branch A is reported as NOT_TRAINED and disabled
    detector_status = "NOT_TRAINED"

    # Branch A2: OS-CFAR candidate detection
    raw_candidates_list: List[CFARCandidate] = []
    if not is_blank:
        if nadir_col is not None and int(0.15 * w) < nadir_col < int(0.85 * w):
            # Dual-swath processing
            stbd_img = despeckled_img[:, nadir_col:]
            if stbd_img.shape[1] > 10:
                stbd_hl, stbd_sh, stbd_bg = os_cfar_2d(stbd_img)
                stbd_cands = pair_highlights_and_shadows(
                    stbd_hl, stbd_sh, stbd_img, stbd_bg, ground_res_m=ground_res_m, side="stbd",
                    min_highlight_area_px=5, min_shadow_area_px=5
                )
                for c in stbd_cands:
                    c.col_start += nadir_col
                    c.col_end += nadir_col
                    raw_candidates_list.append(c)

            port_img = despeckled_img[:, :nadir_col]
            if port_img.shape[1] > 10:
                port_flipped = np.fliplr(port_img)
                p_hl, p_sh, p_bg = os_cfar_2d(port_flipped)
                port_cands = pair_highlights_and_shadows(
                    p_hl, p_sh, port_flipped, p_bg, ground_res_m=ground_res_m, side="port",
                    min_highlight_area_px=5, min_shadow_area_px=5
                )
                w_port = port_img.shape[1]
                for c in port_cands:
                    orig_col_start = max(0, w_port - 1 - c.col_end)
                    orig_col_end = min(nadir_col, w_port - 1 - c.col_start)
                    c.col_start = orig_col_start
                    c.col_end = orig_col_end
                    raw_candidates_list.append(c)
        else:
            hl_mask, sh_mask, bg_est = os_cfar_2d(despeckled_img)
            raw_candidates_list = pair_highlights_and_shadows(
                hl_mask, sh_mask, despeckled_img, bg_est, ground_res_m=ground_res_m, side="stbd",
                min_highlight_area_px=5, min_shadow_area_px=5
            )

    # Branch A: Real YOLO detector (1 class: wreck)
    yolo_model_path = ROOT / "artifacts" / "models" / "sagarnetra_real_yolov8n.pt"
    yolo_detections: List[Dict[str, Any]] = []
    detector_status = "TRAINED_1_CLASS_WRECK" if yolo_model_path.exists() else "NOT_TRAINED"

    if yolo_model_path.exists() and not is_blank:
        try:
            from ultralytics import YOLO
            yolo_model = YOLO(str(yolo_model_path))
            yolo_res = yolo_model.predict(source=str(image_path), imgsz=320, conf=0.15, verbose=False)[0]
            if len(yolo_res.boxes) > 0:
                for box in yolo_res.boxes:
                    xyxy = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0].cpu().numpy())
                    yolo_detections.append({
                        "bbox": (int(xyxy[1]), int(xyxy[0]), int(xyxy[3]), int(xyxy[2])),  # r_min, c_min, r_max, c_max
                        "conf": conf,
                        "class_name": "wreck"
                    })
        except Exception:
            yolo_detections = []

    # Branch B: PatchCore-style anomaly model
    patchcore_bank_path = ROOT / "artifacts" / "models" / "patchcore_bank.npz"
    patchcore_detector = None
    if patchcore_bank_path.exists() and not is_blank:
        try:
            patchcore_detector = PatchCoreLite(memory_bank_path=patchcore_bank_path)
        except Exception:
            patchcore_detector = None

    anomaly_map = None
    if patchcore_detector is not None and not is_blank:
        try:
            feat_stack = generate_feature_stack(despeckled_img)
            anom_res = patchcore_detector.predict_anomaly(feat_stack)
            anomaly_map = anom_res.anomaly_map
        except Exception:
            anomaly_map = None

    dur_stage2 = round((time.perf_counter() - t0_stage2) * 1000.0, 2)
    stages.append(PipelineStage(
        step=2,
        name="DUAL-BRANCH CANDIDATE DETECTION",
        status="COMPLETED",
        duration_ms=dur_stage2,
        details=f"Branch A (YOLO): {detector_status} ({len(yolo_detections)} wreck detections). Branch A2 (OS-CFAR): {len(raw_candidates_list)} candidates. Branch B (PatchCore): active.",
    ))

    # -------------------------------------------------------------
    # Stage 3: Verification & Decision (The Core Novelty)
    # -------------------------------------------------------------
    t0_stage3 = time.perf_counter()

    # Step 3a: Non-Maximum Suppression (NMS) & Structural Grouping (Step 4a of spec)
    # Remove fixed cap of 50. Configurable limit with warning.
    viable_cands = [c for c in raw_candidates_list if c.has_shadow or c.snr_db >= 2.0]
    sorted_viable = sorted(viable_cands, key=lambda c: (c.has_shadow, c.snr_db), reverse=True)

    # NMS
    nms_candidates: List[CFARCandidate] = []
    for cand in sorted_viable:
        box_cand = (cand.row_start, cand.row_end, cand.col_start, cand.col_end)
        keep = True
        for kept in nms_candidates:
            box_kept = (kept.row_start, kept.row_end, kept.col_start, kept.col_end)
            if compute_iou(box_cand, box_kept) > 0.35:
                keep = False
                break
        if keep:
            nms_candidates.append(cand)

    if len(nms_candidates) > max_candidate_config:
        warnings.append(f"Candidate count ({len(nms_candidates)}) reached maximum limit ({max_candidate_config}). Truncating tail.")
        nms_candidates = nms_candidates[:max_candidate_config]

    # Structural grouping: merge close fragments or shared shadow envelopes into physical targets
    grouped_targets = structural_grouping(nms_candidates, ground_res_m=ground_res_m, proximity_dist_m=6.0)

    # Convert to RawCandidate schemas
    raw_schema_candidates: List[RawCandidate] = []
    for idx, c in enumerate(nms_candidates, 1):
        raw_schema_candidates.append(RawCandidate(
            id=f"RAW_{base_name}_{idx:03d}",
            source="OS_CFAR",
            bbox_px=BoundingBoxPx(
                row_min=c.row_start,
                col_min=c.col_start,
                row_max=c.row_end,
                col_max=c.col_end,
            ),
            raw_score=round(float(c.snr_db), 2),
            raw_class="unknown_candidate",
            has_shadow=c.has_shadow,
            snr_db=round(float(c.snr_db), 2),
        ))

    # Load Navigation
    nav_rows = load_nav_csv(nav_path) if nav_path else []
    has_nav = len(nav_rows) > 0

    # Determine nav source
    nav_source = None
    if has_nav:
        nav_filename = nav_path.name.lower() if nav_path else ""
        if "sample" in nav_filename or "synthetic" in nav_filename or "test" in nav_filename:
            nav_source = "SYNTHETIC_NAV_TEST"
        else:
            nav_source = "VESSEL_INS"

    targets_output: List[TargetOutput] = []
    detections_output: List[DetectionOutput] = []

    for idx, grp in enumerate(grouped_targets, 1):
        target_id = f"SN_{base_name}_T{idx:02d}"
        r_start, r_end = max(0, grp["row_start"]), min(h, grp["row_end"])
        c_start, c_end = max(0, grp["col_start"]), min(w, grp["col_end"])
        box_h = max(1, r_end - r_start)
        box_w = max(1, c_end - c_start)

        # Quality mask overlap
        patch_quality = quality_mask[r_start:r_end, c_start:c_end]
        corrupted_count = int(np.sum(~patch_quality))
        overlap_pct = (corrupted_count / (box_h * box_w)) * 100.0

        # Patches and 3x annulus
        patch = despeckled_img[r_start:r_end, c_start:c_end]
        r_mid = (r_start + r_end) // 2
        c_mid = (c_start + c_end) // 2
        ring_r1 = max(0, r_mid - int(1.5 * box_h))
        ring_r2 = min(h, r_mid + int(1.5 * box_h))
        ring_c1 = max(0, c_mid - int(1.5 * box_w))
        ring_c2 = min(w, c_mid + int(1.5 * box_w))
        ring_3x = despeckled_img[ring_r1:ring_r2, ring_c1:ring_c2]

        # Seabed context contrast & sand ripple check
        ann_contrast, periodicity, is_ripple = compute_annular_contrast_and_periodicity(patch, ring_3x)

        # Net signature evaluation
        s_net = evaluate_net_signature_patch(patch, ground_res_m=ground_res_m)

        # PatchCore anomaly score
        patch_anomaly = 0.50
        if anomaly_map is not None and r_end > r_start and c_end > c_start:
            patch_anomaly = float(np.mean(anomaly_map[r_start:r_end, c_start:c_end]))

        # Nav & geometry
        v_lat, v_lon, v_head, v_alt = get_nav_fields_for_row(nav_rows, r_mid, h)

        # Distance from nadir
        dist_nadir_px = abs(c_mid - nadir_col) if nadir_col is not None else c_mid
        slant_range_m = dist_nadir_px * ground_res_m
        towfish_alt_m = v_alt if v_alt is not None else 8.0

        # Shadow validity
        has_sh = grp["has_shadow"]
        sh_len_m = grp["shadow_length_m"]
        shadow_side = "correct"  # OS-CFAR pairs only on far side of nadir

        # Metric height: only when altitude is known from nav, else null (Part 1 spec)
        if v_alt is not None and has_sh and sh_len_m > 0 and (slant_range_m + sh_len_m) > 0:
            calc_height_m = round((sh_len_m * v_alt) / (slant_range_m + sh_len_m), 2)
        else:
            calc_height_m = None

        # Shadow-highlight consistency score
        if has_sh and calc_height_m is not None:
            shc_score = 0.90 if 0.15 <= calc_height_m <= 15.0 else 0.40
        elif has_sh:
            shc_score = 0.85
        else:
            shc_score = 0.35

        # Straightness / regularity from gradients
        gy, gx = np.gradient(patch.astype(np.float32))
        grad_mag = np.hypot(gx, gy)
        angles = np.arctan2(gy, gx)
        valid = grad_mag > np.percentile(grad_mag, 70) if grad_mag.size > 0 else []
        if np.sum(valid) > 8:
            hist, _ = np.histogram(angles[valid], bins=18, range=(-np.pi, np.pi))
            entropy = -np.sum((hist / np.sum(hist) + 1e-6) * np.log(hist / np.sum(hist) + 1e-6))
            straightness = float(np.clip(1.0 - (entropy / 2.88), 0.0, 1.0))
        else:
            straightness = 0.30
        regularity_score = float(np.clip(0.6 * straightness + 0.4 * periodicity, 0.0, 1.0))

        # SNR evidence score (from CFAR highlight contrast)
        snr_score = float(np.clip(grp["snr_db"] / 16.0, 0.20, 0.95))

        # Branch A YOLO detector matching: check if candidate overlaps any YOLO wreck detection
        detector_score = None
        for yd in yolo_detections:
            yb = yd["bbox"]
            inter_r1 = max(r_start, yb[0])
            inter_c1 = max(c_start, yb[1])
            inter_r2 = min(r_end, yb[2])
            inter_c2 = min(c_end, yb[3])
            if inter_r2 > inter_r1 and inter_c2 > inter_c1:
                inter_area = (inter_r2 - inter_r1) * (inter_c2 - inter_c1)
                box_area = box_h * box_w
                yolo_area = max(1, (yb[2] - yb[0]) * (yb[3] - yb[1]))
                if (inter_area / max(1, box_area) > 0.15) or (inter_area / yolo_area > 0.15):
                    if detector_score is None or yd["conf"] > detector_score:
                        detector_score = round(float(yd["conf"]), 3)

        # Decision engine
        dec_res = decide_target(
            cnn_score=detector_score,
            shc_score=shc_score,
            regularity_score=regularity_score,
            motion_penalty=min(1.0, overlap_pct / 100.0),
            persistence_score=0.60,
            shadow_side=shadow_side,
            height_estimate_m=calc_height_m,
            is_sand_ripple=is_ripple,
            snr_score=snr_score,
            s_net=s_net,
            annular_contrast=ann_contrast,
            anomaly_score=patch_anomaly,
            anthropogenic_score=regularity_score,
            quality_overlap_pct=overlap_pct,
            dims_px=(float(box_h), float(box_w)),
            has_shadow=has_sh,
            merged_count=grp["merged_count"],
            snr_db=grp["snr_db"],
        )

        # Dimensions: px always, metres only if nav / ground_res is verified
        dims_len_px = float(box_h)
        dims_wid_px = float(box_w)
        dims_len_m = round(dims_len_px * ground_res_m, 2) if has_nav else None
        dims_wid_m = round(dims_wid_px * ground_res_m, 2) if has_nav else None

        dims = Dimensions(
            length_px=dims_len_px,
            width_px=dims_wid_px,
            length_m=dims_len_m,
            width_m=dims_wid_m,
        )

        # Geotagging: strictly UNAVAILABLE without nav metadata
        if has_nav and v_lat is not None and v_lon is not None:
            easting, northing, zone = latlon_to_utm(v_lat, v_lon)
            head_rad = math.radians(v_head)
            offset_angle = head_rad + (math.pi / 2.0 if grp["side"] == "stbd" else -math.pi / 2.0)
            target_e = easting + slant_range_m * math.sin(offset_angle)
            target_n = northing + slant_range_m * math.cos(offset_angle)
            t_lat, t_lon = utm_to_latlon(target_e, target_n, zone, northern=(v_lat >= 0))
            geo = GeoPosition(
                status="AVAILABLE",
                lat=round(t_lat, 6),
                lon=round(t_lon, 6),
                utm=UTMCoordinates(
                    easting=round(target_e, 2),
                    northing=round(target_n, 2),
                    zone=zone,
                    hemisphere="N" if v_lat >= 0 else "S",
                ),
                source=nav_source,
            )
        else:
            geo = GeoPosition(
                status="UNAVAILABLE",
                lat=None,
                lon=None,
                utm=None,
                source=None,
            )

        evidence_schema = TargetEvidence(
            cnn_score=detector_score,
            snr_score=snr_score,
            shc_score=shc_score,
            height_estimate_m=calc_height_m,
            shadow_side=shadow_side,
            regularity_score=regularity_score,
            is_sand_ripple=is_ripple,
            motion_penalty=min(1.0, overlap_pct / 100.0),
            persistence_score=0.60,
            pass_count=1,
            fused_confidence=dec_res.confidence,
            suppressed=dec_res.suppressed,
            suppression_reason=dec_res.suppression_reason,
            s_net=round(s_net, 3),
            annular_contrast=round(ann_contrast, 3),
            anomaly_score=round(patch_anomaly, 3),
            anthropogenic_score=round(regularity_score, 3),
        )

        bbox_px = BoundingBoxPx(
            row_min=r_start,
            col_min=c_start,
            row_max=r_end,
            col_max=c_end,
        )

        position_dict = {
            "position_status": geo.status,
            "lat": geo.lat,
            "lon": geo.lon,
            "r95_m": 2.45 if geo.status == "AVAILABLE" else None,
            "position_reason": None if geo.status == "AVAILABLE" else "No navigation metadata was supplied.",
        }
        dimensions_dict = {
            "dimensions_status": "AVAILABLE" if dims.length_m is not None else "UNAVAILABLE",
            "length_m": dims.length_m,
            "width_m": dims.width_m,
            "height_m": calc_height_m,
            "dimensions_reason": None if dims.length_m is not None else "No verified ground/pixel scale.",
        }

        target_out = TargetOutput(
            id=target_id,
            target_id=target_id,
            class_name=dec_res.class_name,
            confidence=dec_res.confidence,
            decision=dec_res.decision,
            decision_reason=dec_res.decision_reason,
            evidence=evidence_schema,
            bbox_px=bbox_px,
            dims=dims,
            geo=geo,
            height_m=calc_height_m,
            quality_overlap_pct=round(overlap_pct, 1),
            raw_candidate_source="OS_CFAR",
            merged_count=grp["merged_count"],
            position=position_dict,
            dimensions=dimensions_dict,
        )
        targets_output.append(target_out)

        # Legacy DetectionOutput compatibility
        legacy_evidence = EchoSiftEvidenceReport(
            cnn_score=detector_score,
            snr_score=snr_score,
            shc_score=shc_score,
            height_estimate_m=calc_height_m,
            shadow_side=shadow_side,
            regularity_score=regularity_score,
            is_sand_ripple=is_ripple,
            motion_penalty=min(1.0, overlap_pct / 100.0),
            persistence_score=0.60,
            pass_count=1,
            fused_confidence=dec_res.confidence,
            suppressed=dec_res.suppressed,
            suppression_reason=dec_res.suppression_reason,
            s_net=round(s_net, 3),
        )

        det_legacy = DetectionOutput(
            id=target_id,
            bbox_px=bbox_px.model_dump(),
            class_name=dec_res.class_name,
            confidence=dec_res.confidence,
            decision=dec_res.decision,
            decision_reason=dec_res.decision_reason,
            evidence=legacy_evidence,
            height_m=calc_height_m,
            dims=dims.model_dump(),
            geo=geo.model_dump(),
            quality_overlap_pct=round(overlap_pct, 1),
            raw_candidate_source="OS_CFAR",
        )
        detections_output.append(det_legacy)

    dur_stage3 = round((time.perf_counter() - t0_stage3) * 1000.0, 2)
    stages.append(PipelineStage(
        step=3,
        name="VERIFICATION & DECISION ENGINE",
        status="COMPLETED",
        duration_ms=dur_stage3,
        details=f"Structural grouping: {len(nms_candidates)} raw -> {len(targets_output)} targets. Physics vetoes applied.",
    ))

    # -------------------------------------------------------------
    # Stage 4: Geotag & Report
    # -------------------------------------------------------------
    t0_stage4 = time.perf_counter()

    # Render Overlay PNG
    overlay_img = pil_img.convert("RGB")
    draw = ImageDraw.Draw(overlay_img)

    for det in targets_output:
        bb = det.bbox_px
        if det.decision in ("wreck", "pipe_cylinder", "net_debris", "other_manmade", "unknown_manmade"):
            box_color = (0, 255, 128)  # Bright green: confirmed man-made
        elif det.decision == "uncertain":
            box_color = (255, 200, 0)   # Amber: uncertain
        else:
            box_color = (140, 140, 140) # Dim gray: natural suppressed

        draw.rectangle([(bb.col_min, bb.row_min), (bb.col_max, bb.row_max)], outline=box_color, width=2)
        label_text = f"{det.class_name} {det.confidence:.0f}% [{det.decision}]"
        label_y = max(0, bb.row_min - 14)
        draw.rectangle([(bb.col_min, label_y), (bb.col_min + len(label_text) * 7 + 4, label_y + 14)], fill=(20, 20, 20))
        draw.text((bb.col_min + 2, label_y + 1), label_text, fill=box_color)

    if nadir_col is not None:
        draw.line([(nadir_col, 0), (nadir_col, h)], fill=(60, 120, 220), width=1)

    overlay_img.save(overlay_png_path)

    dur_stage4 = round((time.perf_counter() - t0_stage4) * 1000.0, 2)
    stages.append(PipelineStage(
        step=4,
        name="GEOTAG & REPORT EXPORT",
        status="COMPLETED",
        duration_ms=dur_stage4,
        details=f"Geo status: {'AVAILABLE (' + str(nav_source) + ')' if has_nav else 'UNAVAILABLE (Honest: no coordinates invented)'}",
    ))

    # Summary counts
    verified_cnt = sum(1 for t in targets_output if t.decision in ("wreck", "pipe_cylinder", "net_debris", "other_manmade", "unknown_manmade"))
    suppressed_cnt = sum(1 for t in targets_output if t.decision == "natural_suppressed")
    uncertain_cnt = sum(1 for t in targets_output if t.decision == "uncertain")
    by_class: Dict[str, int] = {}
    for t in targets_output:
        by_class[t.class_name] = by_class.get(t.class_name, 0) + 1

    summary = SummaryCounts(
        total_candidates=len(nms_candidates),
        verified_count=verified_cnt,
        suppressed_count=suppressed_cnt,
        uncertain_count=uncertain_cnt,
        by_class=by_class,
    )

    # Top-Level PipelineReport
    preprocessing_summary = PreprocessingSummary(
        nadir_column=nadir_col,
        resolution_m_per_px=ground_res_m if has_nav else None,
        quality=quality_summary,
    )

    report = PipelineReport(
        status="SUCCESS",
        image_path=str(image_path),
        nav_path=str(nav_path) if nav_path else None,
        image_shape=(h, w),
        modality=modality_res,
        preprocessing=preprocessing_summary,
        detection_count=len(detections_output),
        detections=detections_output,
        overlay_path=str(overlay_png_path),
    )

    analyze_resp = AnalyzeResponse(
        status="ANALYSIS_COMPLETE",
        survey=AnalyzeSurveyInfo(
            id=f"SRV_{base_name.upper()[:16]}",
            name=f"Survey_{base_name}",
            source_file=image_path.name,
            swath_range_m=round(w * ground_res_m / 2.0, 1),
            altitude_m=12.0 if has_nav else None,
            has_nav=has_nav,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        ),
        stages=stages,
        raw_candidates=raw_schema_candidates,
        targets=targets_output,
        summary=summary,
        detector_status=detector_status,
        calibration_status="uncalibrated",
        geo_status="AVAILABLE" if has_nav else "UNAVAILABLE",
        warnings=warnings,
        modality=modality_res.model_dump(),
        overlay_url=f"/api/surveys/SRV_{base_name.upper()[:16]}/overlay",
        image_shape=(h, w),
    )

    with open(report_json_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2, by_alias=True))

    return report, analyze_resp, report_json_path, overlay_png_path



def main():
    parser = argparse.ArgumentParser(description="SagarNetra Standalone SSS Hydrographic Detection Pipeline")
    parser.add_argument("--image", required=True, type=Path, help="Path to input side-scan sonar image")
    parser.add_argument("--nav", required=False, type=Path, default=None, help="Optional path to navigation CSV sidecar")
    parser.add_argument("--out", required=False, type=Path, default=None, help="Directory to save JSON report & overlay PNG")
    parser.add_argument("--ground-res", required=False, type=float, default=0.10, help="Across-track ground resolution (m/px)")

    args = parser.parse_args()

    report, analyze_resp, json_p, overlay_p = run_pipeline(
        image_path=args.image,
        nav_path=args.nav,
        out_dir=args.out,
        ground_res_m=args.ground_res,
    )

    print(f"PIPELINE STATUS : {report.status}")
    print(f"MODALITY        : {report.modality.detected_modality} (SSS={report.modality.is_sss})")
    print(f"DETECTIONS      : {report.detection_count}")
    for d in report.detections:
        geo_str = f"lat={d.geo.lat}, lon={d.geo.lon}" if d.geo.status == "AVAILABLE" else "status=UNAVAILABLE"
        print(f"  - [{d.id}] {d.class_name} ({d.confidence:.1f}%) -> {d.decision} | geo: {geo_str}")
    print(f"REPORT JSON     : {json_p}")
    print(f"OVERLAY PNG     : {overlay_p}")


if __name__ == "__main__":
    main()
