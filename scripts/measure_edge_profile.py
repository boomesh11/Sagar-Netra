"""
scripts/measure_edge_profile.py
===============================
Measures real ONNX Runtime inference time per 640px tile on this machine (CPU)
and full-pipeline execution time per image.
"""
import time
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import onnxruntime as ort
from scripts.run_pipeline import run_pipeline

ROOT = Path(__file__).resolve().parent.parent

def benchmark():
    onnx_path = ROOT / "artifacts" / "models" / "sagarnetra_real_yolov8n.onnx"
    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=======================================================")
    print("SagarNetra Phase 9: Edge Profile Benchmarking (CPU)")
    print("=======================================================")

    results = {}

    # 1. Benchmark ONNX Runtime per 640px tile
    if onnx_path.exists():
        print("[1/2] Benchmarking ONNX Runtime inference on CPU (320x320 / 640x640)...")
        session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        input_name = session.get_inputs()[0].name
        shape = session.get_inputs()[0].shape
        # Input tensor
        h = shape[2] if isinstance(shape[2], int) else 320
        w = shape[3] if isinstance(shape[3], int) else 320
        dummy_input = np.random.rand(1, 3, h, w).astype(np.float32)

        # Warmup
        for _ in range(5):
            session.run(None, {input_name: dummy_input})

        latencies_ms = []
        n_iters = 50
        for _ in range(n_iters):
            t0 = time.perf_counter()
            session.run(None, {input_name: dummy_input})
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)

        mean_onnx_lat = float(np.mean(latencies_ms))
        std_onnx_lat = float(np.std(latencies_ms))
        throughput_tiles = float(1000.0 / mean_onnx_lat)

        print(f"ONNX Latency (mean +/- std): {mean_onnx_lat:.2f} +/- {std_onnx_lat:.2f} ms")
        print(f"ONNX Throughput:            {throughput_tiles:.1f} tiles/sec")

        results["onnx_runtime"] = {
            "platform": "CPU (Intel / AMD x86_64)",
            "precision": "FP32 ONNX Runtime",
            "mean_latency_ms": round(mean_onnx_lat, 2),
            "std_latency_ms": round(std_onnx_lat, 2),
            "throughput_tiles_per_sec": round(throughput_tiles, 1)
        }
    else:
        print("[!] ONNX model not found, skipping direct ONNX benchmark.")

    # 2. Benchmark Full Python Pipeline
    test_img = ROOT / "tests" / "fixtures" / "real_sss_tile_wreck.png"
    if test_img.exists():
        print("\n[2/2] Benchmarking Full Standalone Pipeline (Preprocessing + CFAR + EchoSift + Reports)...")
        tmp_dir = ROOT / "reports" / "bench_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        # Warmup
        run_pipeline(image_path=test_img, out_dir=tmp_dir)

        pipe_latencies_ms = []
        n_pipe_iters = 5
        for _ in range(n_pipe_iters):
            t0 = time.perf_counter()
            run_pipeline(image_path=test_img, out_dir=tmp_dir)
            pipe_latencies_ms.append((time.perf_counter() - t0) * 1000.0)

        mean_pipe_lat = float(np.mean(pipe_latencies_ms))
        std_pipe_lat = float(np.std(pipe_latencies_ms))

        print(f"Full Pipeline Latency:       {mean_pipe_lat:.2f} +/- {std_pipe_lat:.2f} ms")

        results["full_pipeline"] = {
            "mean_latency_ms": round(mean_pipe_lat, 2),
            "std_latency_ms": round(std_pipe_lat, 2),
            "stages": 20
        }

    bench_path = out_dir / "edge_benchmarks.json"
    with open(bench_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved benchmark telemetry to: {bench_path}")

if __name__ == "__main__":
    benchmark()
