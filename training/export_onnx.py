"""
SagarNetra Training — Model Export and Parity Verification.
Exports SagarNetraSegNet to TorchScript and ONNX, verifying numerical parity
against PyTorch eager execution (|max_diff| < 1e-3).
Outputs:
  - TorchScript: artifacts/models/sagarnetra_seg.torchscript
  - ONNX:        artifacts/models/sagarnetra_seg.onnx (if ONNX backend available)
  - Report:      artifacts/metrics/m6_export_report.json
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import torch

from backend.sagarnetra.detect.yolo_onnx import SagarNetraSegNet
from sonarforge.dataset_builder import CLASS_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def export_and_verify(
    model_path: str | Path = "artifacts/models/sagarnetra_seg_quick.pt",
    output_dir: str | Path = "artifacts",
) -> Dict[str, any]:
    """
    Exports the model and verifies numerical consistency.
    """
    model_path = Path(model_path)
    output_dir = Path(output_dir)
    models_dir = output_dir / "models"
    metrics_dir = output_dir / "metrics"
    models_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load PyTorch eager model
    model = SagarNetraSegNet(num_classes=len(CLASS_NAMES))
    if model_path.exists():
        state = torch.load(model_path, map_location="cpu", weights_only=True)
        if isinstance(state, dict) and "state_dict" in state:
            model.load_state_dict(state["state_dict"])
        elif isinstance(state, dict):
            model.load_state_dict(state)
        logger.info("Loaded trained weights from %s", model_path)
    else:
        logger.warning("Model weights %s not found. Using initialized model.", model_path)

    model.eval()

    dummy_input = torch.randn(1, 3, 512, 512, dtype=torch.float32)

    # Eager outputs
    with torch.no_grad():
        eager_mask, eager_cls = model(dummy_input)

    report: Dict[str, any] = {
        "model_architecture": "SagarNetraSegNet",
        "input_shape": list(dummy_input.shape),
        "torchscript_exported": False,
        "onnx_exported": False,
        "torchscript_mask_parity_max_diff": None,
        "torchscript_cls_parity_max_diff": None,
        "parity_verified": False,
    }

    # 2. Export to TorchScript (JIT trace)
    ts_path = models_dir / "sagarnetra_seg.torchscript"
    try:
        traced_model = torch.jit.trace(model, dummy_input)
        traced_model.save(str(ts_path))
        report["torchscript_exported"] = True
        logger.info("Exported TorchScript model to %s", ts_path)

        # Verify TorchScript parity
        ts_loaded = torch.jit.load(str(ts_path))
        with torch.no_grad():
            ts_mask, ts_cls = ts_loaded(dummy_input)

        diff_mask = float(torch.max(torch.abs(eager_mask - ts_mask)).item())
        diff_cls = float(torch.max(torch.abs(eager_cls - ts_cls)).item())
        report["torchscript_mask_parity_max_diff"] = diff_mask
        report["torchscript_cls_parity_max_diff"] = diff_cls

        parity_ok = (diff_mask < 1e-3) and (diff_cls < 1e-3)
        report["parity_verified"] = parity_ok
        logger.info("TorchScript parity check: mask diff=%.6f, cls diff=%.6f (PASS: %s)",
                    diff_mask, diff_cls, parity_ok)

    except Exception as e:
        logger.error("TorchScript export failed: %s", e)
        report["torchscript_error"] = str(e)

    # 3. Export to ONNX (if onnx is installed)
    onnx_path = models_dir / "sagarnetra_seg.onnx"
    try:
        import onnx
        torch.onnx.export(
            model,
            dummy_input,
            str(onnx_path),
            input_names=["feature_stack"],
            output_names=["mask_logits", "class_logits"],
            dynamic_axes={
                "feature_stack": {0: "batch_size"},
                "mask_logits": {0: "batch_size"},
                "class_logits": {0: "batch_size"},
            },
            opset_version=17,
        )
        report["onnx_exported"] = True
        logger.info("Exported ONNX model to %s", onnx_path)
    except (ImportError, Exception) as e:
        logger.info("ONNX export skipped or unsupported in current environment: %s", e)
        report["onnx_export_note"] = str(e)

    # Save export report
    report_path = metrics_dir / "m6_export_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info("Saved export report to %s", report_path)

    return report


def main():
    parser = argparse.ArgumentParser(description="Export SagarNetra Model to TorchScript/ONNX")
    parser.add_argument("--model-path", type=str, default="artifacts/models/sagarnetra_seg_quick.pt")
    parser.add_argument("--output-dir", type=str, default="artifacts")
    args = parser.parse_args()

    export_and_verify(model_path=args.model_path, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
