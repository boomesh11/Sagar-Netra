"""
SagarNetra Training — Temperature Calibration & Reliability Curve Generator.
Fits temperature scaling on validation set predictions, generates reliability diagram plot,
and evaluates ECE reduction.
Outputs:
  - Temperature config: artifacts/models/temperature_calibration.json
  - Reliability plot:   artifacts/plots/reliability_diagram.png
  - Metrics JSON:       artifacts/metrics/m7_calibration_metrics.json
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict

import numpy as np
import torch
from torch.utils.data import DataLoader

from backend.sagarnetra.confidence.calibrate import TemperatureScaler, compute_ece, plot_reliability_diagram
from backend.sagarnetra.detect.yolo_onnx import SagarNetraSegNet
from sonarforge.dataset_builder import CLASS_NAMES
from training.train_yolo import SonarSegDataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_calibration(
    dataset_dir: str | Path = "data/datasets/sagarnetra_v1",
    model_path: str | Path = "artifacts/models/sagarnetra_seg_quick.pt",
    output_dir: str | Path = "artifacts",
) -> Dict[str, any]:
    dataset_dir = Path(dataset_dir)
    output_dir = Path(output_dir)
    models_dir = output_dir / "models"
    plots_dir = output_dir / "plots"
    metrics_dir = output_dir / "metrics"
    models_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load trained model
    model = SagarNetraSegNet(num_classes=len(CLASS_NAMES))
    if Path(model_path).exists():
        state = torch.load(model_path, map_location="cpu", weights_only=True)
        if isinstance(state, dict) and "state_dict" in state:
            model.load_state_dict(state["state_dict"])
        elif isinstance(state, dict):
            model.load_state_dict(state)
        logger.info("Loaded model weights from %s", model_path)
    else:
        logger.warning("No model found at %s. Using initialized model.", model_path)

    model.eval()

    # 2. Extract validation logits and ground truth
    val_set = SonarSegDataset(dataset_dir / "val", max_samples=20)
    val_loader = DataLoader(val_set, batch_size=4, shuffle=False)

    all_logits = []
    all_targets = []

    with torch.no_grad():
        for imgs, _, targets in val_loader:
            _, cls_logits = model(imgs)
            all_logits.append(cls_logits.numpy().flatten())
            all_targets.append(targets.numpy().flatten())

    if len(all_logits) == 0:
        raise ValueError("No validation samples available for calibration")

    flat_logits = np.concatenate(all_logits, axis=0)
    flat_targets = np.concatenate(all_targets, axis=0)

    # Uncalibrated probabilities
    uncal_probs = 1.0 / (1.0 + np.exp(-flat_logits))
    uncal_ece_res = compute_ece(uncal_probs, flat_targets, num_bins=10)

    # 3. Fit Temperature Scaler
    scaler = TemperatureScaler()
    opt_temp = scaler.fit(flat_logits, flat_targets)
    logger.info("Optimized temperature T = %.3f", opt_temp)

    # Calibrated probabilities
    cal_logits = flat_logits / opt_temp
    cal_probs = 1.0 / (1.0 + np.exp(-cal_logits))
    cal_ece_res = compute_ece(cal_probs, flat_targets, num_bins=10)

    logger.info("Uncalibrated ECE: %.4f | Calibrated ECE: %.4f", uncal_ece_res["ece"], cal_ece_res["ece"])

    # 4. Save calibration params and plot
    scaler.save(models_dir / "temperature_calibration.json")

    plot_path = plots_dir / "reliability_diagram.png"
    try:
        plot_reliability_diagram(uncal_probs, cal_probs, flat_targets, save_path=plot_path)
        logger.info("Saved reliability diagram to %s", plot_path)
    except Exception as e:
        logger.warning("Could not render reliability diagram plot: %s", e)

    metrics_data = {
        "temperature": round(opt_temp, 3),
        "uncalibrated_ece": uncal_ece_res["ece"],
        "calibrated_ece": cal_ece_res["ece"],
        "uncalibrated_brier": uncal_ece_res["brier_score"],
        "calibrated_brier": cal_ece_res["brier_score"],
        "target_ece_achieved": bool(cal_ece_res["ece"] <= 0.10),
        "num_validation_instances": len(flat_logits),
    }

    metrics_path = metrics_dir / "m7_calibration_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=2)
    logger.info("Saved calibration metrics to %s", metrics_path)

    return metrics_data


def main():
    parser = argparse.ArgumentParser(description="Calibrate Confidence with Temperature Scaling")
    parser.add_argument("--dataset-dir", type=str, default="data/datasets/sagarnetra_v1")
    parser.add_argument("--model-path", type=str, default="artifacts/models/sagarnetra_seg_quick.pt")
    parser.add_argument("--output-dir", type=str, default="artifacts")
    args = parser.parse_args()

    run_calibration(args.dataset_dir, args.model_path, args.output_dir)


if __name__ == "__main__":
    main()
