#!/usr/bin/env python3
"""
scripts/rebuild_patchcore_real.py
=================================
Rebuilds the PatchCore-Lite nominal seabed memory bank exclusively from
REAL hydrographic natural seabed tiles (AI4Shipwrecks TRAIN background tiles
and fixtures). Strictly NO SonarForge synthetic tiles.

Outputs:
  - artifacts/models/patchcore_bank.npz
  - artifacts/models/patchcore_sources.json
  - reports/patchcore_evaluation.json (AUROC on held-out test split)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import numpy as np
from PIL import Image
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent.parent

import sys
sys.path.insert(0, str(ROOT))

from backend.sagarnetra.detect.anomaly import PatchCoreLite
from backend.sagarnetra.preprocess.despeckle import enhanced_lee_filter
from backend.sagarnetra.preprocess.features import generate_feature_stack

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rebuild_patchcore")

def collect_real_seabed_sources() -> list[Path]:
    train_img_dir = ROOT / "data" / "datasets" / "real_ai4shipwrecks_yolo" / "train" / "images"
    train_lbl_dir = ROOT / "data" / "datasets" / "real_ai4shipwrecks_yolo" / "train" / "labels"

    real_sources: list[Path] = []

    # 1. Official negative fixture
    neg_fixture = ROOT / "tests" / "fixtures" / "natural_seabed_negative.png"
    if neg_fixture.exists():
        real_sources.append(neg_fixture)

    # 2. Pure background tiles from training set (no annotations)
    if train_img_dir.exists():
        for img_p in sorted(train_img_dir.glob("*.png")):
            lbl_p = train_lbl_dir / f"{img_p.stem}.txt"
            if not lbl_p.exists() or lbl_p.stat().st_size == 0:
                real_sources.append(img_p)

    logger.info("Found %d real natural seabed background sources (0 synthetic)", len(real_sources))
    return real_sources

def process_tile_to_features(img_path: Path) -> np.ndarray:
    im = Image.open(img_path).convert("L")
    arr = np.array(im, dtype=np.float32) / 255.0
    desp = enhanced_lee_filter(arr, window_size=7)
    feats = generate_feature_stack(desp)
    return feats

def main():
    print("=================================================================")
    print("Rebuilding PatchCore Memory Bank from REAL Natural Seabed Only")
    print("Rule G1/G2: Strictly NO SonarForge or synthetic tiles")
    print("=================================================================")

    sources = collect_real_seabed_sources()
    if not sources:
        raise RuntimeError("No real natural seabed tiles found!")

    # Subsample 40 tiles for memory bank construction to keep memory & coreset fast
    selected_sources = sources[:40]
    nominal_stacks = []
    source_records = []

    for idx, p in enumerate(selected_sources):
        try:
            feats = process_tile_to_features(p)
            nominal_stacks.append(feats)
            source_records.append({
                "index": idx,
                "file": str(p.relative_to(ROOT)),
                "source": "AI4Shipwrecks_NOAA_EdgeTech2205",
                "is_synthetic": False
            })
        except Exception as e:
            logger.warning("Failed processing %s: %s", p, e)

    logger.info("Processed %d nominal feature stacks.", len(nominal_stacks))

    # Build memory bank
    detector = PatchCoreLite()
    logger.info("Building coreset memory bank (coreset_ratio=0.08)...")
    detector.build_memory_bank(nominal_stacks, coreset_ratio=0.08)

    models_dir = ROOT / "artifacts" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    bank_path = models_dir / "patchcore_bank.npz"
    detector.save_memory_bank(bank_path)
    logger.info("Saved new real PatchCore bank to %s (size %d patches)", bank_path, len(detector.memory_bank))

    # Save sources record
    sources_json_path = models_dir / "patchcore_sources.json"
    with open(sources_json_path, "w") as f:
        json.dump({
            "status": "BUILT_FROM_REAL_SEABED_ONLY",
            "coreset_patches": len(detector.memory_bank),
            "total_training_tiles": len(nominal_stacks),
            "synthetic_tiles_count": 0,
            "sources": source_records
        }, f, indent=2)
    logger.info("Saved sources record to %s", sources_json_path)

    # Evaluate AUROC on held-out test split
    print("\nEvaluating Anomaly AUROC on AI4Shipwrecks TEST Split...")
    test_img_dir = ROOT / "data" / "datasets" / "real_ai4shipwrecks_yolo" / "test" / "images"
    test_lbl_dir = ROOT / "data" / "datasets" / "real_ai4shipwrecks_yolo" / "test" / "labels"

    test_bg_imgs = []
    test_wreck_imgs = []

    for img_p in sorted(test_img_dir.glob("*.png")):
        lbl_p = test_lbl_dir / f"{img_p.stem}.txt"
        if not lbl_p.exists() or lbl_p.stat().st_size == 0:
            test_bg_imgs.append(img_p)
        else:
            test_wreck_imgs.append(img_p)

    logger.info("Found %d test BG tiles and %d test wreck tiles.", len(test_bg_imgs), len(test_wreck_imgs))

    # Evaluate 40 BG tiles vs 40 wreck tiles for AUROC
    eval_bgs = test_bg_imgs[:40]
    eval_wrecks = test_wreck_imgs[:40]

    y_true = []
    y_scores = []

    # Negatives (label = 0)
    for p in eval_bgs:
        try:
            feats = process_tile_to_features(p)
            anom_res = detector.predict_anomaly(feats)
            y_true.append(0)
            y_scores.append(float(anom_res.anomaly_score))
        except Exception as e:
            logger.warning("Error evaluating BG %s: %s", p, e)

    # Positives (label = 1)
    for p in eval_wrecks:
        try:
            feats = process_tile_to_features(p)
            anom_res = detector.predict_anomaly(feats)
            y_true.append(1)
            y_scores.append(float(anom_res.anomaly_score))
        except Exception as e:
            logger.warning("Error evaluating wreck %s: %s", p, e)

    auroc = float(roc_auc_score(y_true, y_scores)) if len(set(y_true)) > 1 else 0.5
    mean_bg_score = float(np.mean([s for y, s in zip(y_true, y_scores) if y == 0]))
    mean_wreck_score = float(np.mean([s for y, s in zip(y_true, y_scores) if y == 1]))

    print(f"\n=======================================================")
    print(f"PatchCore Anomaly AUROC (Test Split): {auroc:.4f}")
    print(f"Mean Anomaly Score (Seabed BG): {mean_bg_score:.4f}")
    print(f"Mean Anomaly Score (Wrecks):    {mean_wreck_score:.4f}")
    print(f"=======================================================")

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    eval_json_path = reports_dir / "patchcore_evaluation.json"
    with open(eval_json_path, "w") as f:
        json.dump({
            "status": "EVALUATED_ON_REAL_TEST_SPLIT",
            "model": "PatchCoreLite",
            "auroc": round(auroc, 4),
            "test_samples_evaluated": len(y_true),
            "negative_samples": int(np.sum(np.array(y_true) == 0)),
            "positive_samples": int(np.sum(np.array(y_true) == 1)),
            "mean_background_anomaly_score": round(mean_bg_score, 4),
            "mean_wreck_anomaly_score": round(mean_wreck_score, 4),
            "memory_bank_size": len(detector.memory_bank)
        }, f, indent=2)

    logger.info("Saved PatchCore test evaluation to %s", eval_json_path)

if __name__ == "__main__":
    main()
