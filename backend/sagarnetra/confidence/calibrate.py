"""
SagarNetra Confidence — Temperature Scaling Calibration & ECE Evaluation.
Calibrates classifier probabilities via learned temperature parameter T:
  - Fits T > 0 on validation set logits using negative log likelihood
  - Computes Expected Calibration Error (ECE <= 0.05 target) and MCE
  - Produces reliability diagram data and plots
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import minimize_scalar




def compute_ece(
    probs: np.ndarray,
    labels: np.ndarray,
    num_bins: int = 10,
) -> Dict[str, any]:
    """
    Computes Expected Calibration Error (ECE) and reliability bin stats.
    
    Args:
        probs: 1D array of predicted confidences in [0, 1]
        labels: 1D array of binary ground truth (0 or 1)
        num_bins: Number of equal-width confidence intervals
    """
    probs = np.asarray(probs, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)

    bin_boundaries = np.linspace(0.0, 1.0, num_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]

    ece = 0.0
    mce = 0.0
    bin_stats = []
    total_samples = len(probs)

    for bin_idx, (b_low, b_high) in enumerate(zip(bin_lowers, bin_uppers)):
        if bin_idx == num_bins - 1:
            in_bin = (probs >= b_low) & (probs <= b_high)
        else:
            in_bin = (probs >= b_low) & (probs < b_high)

        bin_size = int(np.sum(in_bin))
        if bin_size > 0:
            bin_acc = float(np.mean(labels[in_bin]))
            bin_conf = float(np.mean(probs[in_bin]))
            gap = abs(bin_acc - bin_conf)
            weight = bin_size / total_samples
            ece += weight * gap
            mce = max(mce, gap)
        else:
            bin_acc = 0.0
            bin_conf = float((b_low + b_high) / 2.0)
            gap = 0.0

        bin_stats.append({
            "bin_idx": bin_idx,
            "range": [round(float(b_low), 2), round(float(b_high), 2)],
            "count": bin_size,
            "accuracy": round(float(bin_acc), 4),
            "confidence": round(float(bin_conf), 4),
            "gap": round(float(gap), 4),
        })

    brier_score = float(np.mean((probs - labels) ** 2)) if total_samples > 0 else 0.0

    return {
        "ece": round(float(ece), 4),
        "mce": round(float(mce), 4),
        "brier_score": round(float(brier_score), 4),
        "num_samples": total_samples,
        "bins": bin_stats,
    }


class TemperatureScaler:
    """
    Learns and applies temperature scaling to logits.
    """
    def __init__(self, temperature: float = 1.0):
        self.temperature = float(temperature)

    def fit(self, logits: np.ndarray, targets: np.ndarray) -> float:
        """
        Finds optimal temperature T > 0 that minimizes binary cross-entropy.
        """
        logits = np.asarray(logits, dtype=np.float64)
        targets = np.asarray(targets, dtype=np.float64)

        def loss_fn(t_val: float) -> float:
            scaled = logits / max(t_val, 1e-4)
            # Binary cross entropy with numerical stability
            p = 1.0 / (1.0 + np.exp(-np.clip(scaled, -30.0, 30.0)))
            eps = 1e-7
            bce = -np.mean(targets * np.log(p + eps) + (1.0 - targets) * np.log(1.0 - p + eps))
            return float(bce)

        res = minimize_scalar(loss_fn, bounds=(0.05, 5.0), method="bounded")
        self.temperature = float(res.x)
        return self.temperature

    def scale_probability(self, prob: float) -> float:
        """
        Converts uncalibrated probability to calibrated probability via logit scaling.
        """
        eps = 1e-6
        p = np.clip(prob, eps, 1.0 - eps)
        logit = np.log(p / (1.0 - p))
        scaled_logit = logit / self.temperature
        cal_p = 1.0 / (1.0 + np.exp(-np.clip(scaled_logit, -30.0, 30.0)))
        return float(np.clip(cal_p, 0.0, 1.0))

    def scale_logits(self, logits: np.ndarray) -> np.ndarray:
        return np.asarray(logits) / self.temperature

    def save(self, file_path: str | Path) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"temperature": self.temperature}, f, indent=2)

    def load(self, file_path: str | Path) -> None:
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.temperature = float(data["temperature"])


def plot_reliability_diagram(
    uncal_probs: np.ndarray,
    cal_probs: np.ndarray,
    labels: np.ndarray,
    save_path: str | Path = "artifacts/plots/reliability_diagram.png",
) -> None:
    """
    Renders and saves reliability diagram comparing before and after calibration.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    uncal_res = compute_ece(uncal_probs, labels, num_bins=10)
    cal_res = compute_ece(cal_probs, labels, num_bins=10)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5), sharey=True)

    for ax, res, title in [
        (ax1, uncal_res, f"Uncalibrated (ECE: {uncal_res['ece']:.3f})"),
        (ax2, cal_res, f"Temperature Scaled (ECE: {cal_res['ece']:.3f})"),
    ]:
        confs = [b["confidence"] for b in res["bins"]]
        accs = [b["accuracy"] for b in res["bins"]]
        counts = [b["count"] for b in res["bins"]]

        ax.plot([0, 1], [0, 1], "k--", label="Perfect Calibration")
        ax.bar(np.linspace(0.05, 0.95, 10), accs, width=0.08, alpha=0.6, color="#008080", edgecolor="navy", label="Outputs")
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_xlabel("Confidence", fontsize=10)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(True, linestyle=":", alpha=0.6)

    ax1.set_ylabel("Empirical Accuracy", fontsize=10)
    ax1.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(str(save_path), dpi=200)
    plt.close()
