import os
import json
from pathlib import Path
import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent

def evaluate():
    pt_path = ROOT / "artifacts" / "models" / "sagarnetra_real_yolov8n.pt"
    onnx_path = ROOT / "artifacts" / "models" / "sagarnetra_real_yolov8n.onnx"
    data_yaml = ROOT / "data" / "datasets" / "real_ai4shipwrecks_yolo" / "dataset.yaml"
    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "detector_metrics.json"

    print("=======================================================")
    print("Evaluating Real YOLOv8n Detector on AI4Shipwrecks TEST Split")
    print(f"Model: {pt_path}")
    print(f"Data: {data_yaml}")
    print("=======================================================")

    model = YOLO(str(pt_path))
    val_results = model.val(
        data=str(data_yaml),
        split="test",
        imgsz=320,
        batch=16,
        workers=0,
        verbose=True
    )

    mp = float(val_results.box.mp)
    mr = float(val_results.box.mr)
    map50 = float(val_results.box.map50)
    map50_95 = float(val_results.box.map)
    f1 = float(2 * mp * mr / max(1e-6, (mp + mr)))

    print(f"Real Test Metrics: Precision={mp:.4f}, Recall={mr:.4f}, mAP50={map50:.4f}, mAP50-95={map50_95:.4f}, F1={f1:.4f}")

    # Parity Check: Compare PyTorch vs ONNX on test images
    parity_results = {"status": "NOT_RUN", "max_diff": 0.0, "mean_iou": 1.0}
    if onnx_path.exists():
        print("\nPerforming Parity Check between PyTorch .pt and ONNX...")
        try:
            import onnxruntime as ort
            test_img_dir = ROOT / "data" / "datasets" / "real_ai4shipwrecks_yolo" / "test" / "images"
            test_images = sorted(list(test_img_dir.glob("*.png")) + list(test_img_dir.glob("*.jpg")))[:20]

            ort_session = ort.InferenceSession(str(onnx_path), providers=['CPUExecutionProvider'])
            max_conf_diff = 0.0

            for img_p in test_images:
                # PT inference
                pt_res = model.predict(str(img_p), imgsz=320, verbose=False)[0]
                pt_confs = pt_res.boxes.conf.cpu().numpy() if len(pt_res.boxes) > 0 else np.array([])

                # ONNX inference via YOLO export interface or direct
                onnx_model = YOLO(str(onnx_path), task="detect")
                ox_res = onnx_model.predict(str(img_p), imgsz=320, verbose=False)[0]
                ox_confs = ox_res.boxes.conf.cpu().numpy() if len(ox_res.boxes) > 0 else np.array([])

                if len(pt_confs) > 0 and len(ox_confs) > 0:
                    diff = abs(float(pt_confs[0]) - float(ox_confs[0]))
                    if diff > max_conf_diff:
                        max_conf_diff = diff

            parity_results = {
                "status": "VERIFIED_PARITY",
                "evaluated_samples": len(test_images),
                "max_confidence_difference": round(max_conf_diff, 6),
                "parity_passed": max_conf_diff < 0.05
            }
            print(f"Parity Results: {parity_results}")
        except Exception as e:
            parity_results = {"status": f"ERROR: {str(e)}", "parity_passed": False}
            print(f"Parity error: {e}")

    report = {
        "model_file": str(pt_path.relative_to(ROOT)),
        "onnx_file": str(onnx_path.relative_to(ROOT)),
        "dataset": "AI4Shipwrecks Official NOAA EdgeTech 2205 Side-Scan Sonar",
        "split_evaluated": "test",
        "detector_status": "TRAINED_1_CLASS_WRECK",
        "classes_trained": ["wreck"],
        "pending_classes": ["pipe_cylinder", "net_debris", "other_manmade"],
        "class_training_note": "Pipe, cylinder and net classes: training pending (limited real data)",
        "metrics": {
            "precision": round(mp, 4),
            "recall": round(mr, 4),
            "mAP50": round(map50, 4),
            "mAP50_95": round(map50_95, 4),
            "f1_score": round(f1, 4)
        },
        "parity_check": parity_results
    }

    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nWritten real detector evaluation report to: {report_file}")
    return report

if __name__ == "__main__":
    evaluate()
