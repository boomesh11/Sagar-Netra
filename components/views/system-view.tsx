"use client";

import React from "react";
import { Activity, Info, CheckCircle2, ShieldCheck } from "lucide-react";

export function SystemView({ subTab }: { subTab: "edge-profile" | "model-info" | "tests" }) {
  return (
    <div className="p-6 space-y-4 max-w-full overflow-y-auto h-full">
      {/* Tab: Edge Profile */}
      {subTab === "edge-profile" && (
        <div className="space-y-4">
          <div className="pb-3 border-b border-border">
            <div className="section-label">HARDWARE DEPLOYMENT SPECIFICATION</div>
            <h1 className="text-[20px] font-semibold text-text mt-0.5">
              Edge Runtime Profiles &amp; Benchmark Objectives
            </h1>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="panel p-4 space-y-3">
              <div className="section-label">PROFILE 1: ONBOARD EDGE (JETSON ORIN NANO)</div>
              <div className="space-y-2 text-[13px]">
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Target Platform:</span>
                  <span className="font-mono font-medium text-text">NVIDIA Jetson Orin Nano (8GB)</span>
                </div>
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Precision:</span>
                  <span className="font-mono font-medium text-text">INT8 TensorRT</span>
                </div>
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Memory Footprint:</span>
                  <span className="font-mono font-medium text-text">3.2 MB (Quantized)</span>
                </div>
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Inference Latency:</span>
                  <span className="font-mono font-medium text-accent">Target: &lt; 15 ms (pending field benchmark)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">Throughput:</span>
                  <span className="font-mono font-medium text-accent">Target: &ge; 25 tiles/s (pending field benchmark)</span>
                </div>
              </div>
            </div>

            <div className="panel p-4 space-y-3">
              <div className="section-label">PROFILE 2: SHORE RESEARCH WORKSTATION</div>
              <div className="space-y-2 text-[13px]">
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Target Platform:</span>
                  <span className="font-mono font-medium text-text">x86_64 Laptop / Intel NUC</span>
                </div>
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Precision:</span>
                  <span className="font-mono font-medium text-text">FP32 ONNX Runtime</span>
                </div>
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Memory Footprint:</span>
                  <span className="font-mono font-medium text-text">6.8 MB</span>
                </div>
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Inference Latency:</span>
                  <span className="font-mono font-medium text-text">13.80 ms (Measured CPU ONNX)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">Throughput:</span>
                  <span className="font-mono font-medium text-text">72.5 tiles/s (Measured CPU ONNX)</span>
                </div>
              </div>
            </div>
          </div>

          <div className="p-3 bg-surface-2 border border-border rounded text-[12px] text-text-muted font-mono">
            Scientific Policy: Performance numbers marked as "Target — pending benchmark" maintain honesty until field-trial hardware telemetry is logged aboard NIOT vessels.
          </div>
        </div>
      )}

      {/* Tab: Model Info */}
      {subTab === "model-info" && (
        <div className="space-y-4">
          <div className="pb-3 border-b border-border">
            <div className="section-label">AI ARCHITECTURE &amp; TAXONOMY</div>
            <h1 className="text-[20px] font-semibold text-text mt-0.5">
              Detector Architecture &amp; Physical Verification Contract
            </h1>
          </div>

          {/* Official Dataset & Trained Weights Card */}
          <div className="panel p-4 space-y-3 border-l-4 border-l-primary">
            <div className="flex justify-between items-center">
              <div className="section-label text-primary font-bold">OFFICIAL HYDROGRAPHIC TRAINING DATASET &amp; WEIGHTS</div>
              <span className="px-2 py-0.5 text-[11px] font-mono bg-success/10 text-success border border-success/30 rounded font-semibold">
                TRAINED ON REAL DATA
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-[13px]">
              <div className="space-y-2">
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Dataset Source:</span>
                  <span className="font-mono font-medium text-text">AI4Shipwrecks (NOAA / Thunder Bay NMS)</span>
                </div>
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Sonar Instrument:</span>
                  <span className="font-mono font-medium text-text">EdgeTech 2205 Dual-Frequency SSS</span>
                </div>
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Acoustic Modality:</span>
                  <span className="font-mono font-medium text-text">Single-channel backscatter (No synthetic noise)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">Leakage Guard:</span>
                  <span className="font-mono font-medium text-success">Strict site-level split (Zero spatial overlap)</span>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Training Set:</span>
                  <span className="font-mono font-medium text-text">1,550 tiles (640×640 single-channel)</span>
                </div>
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Validation Set:</span>
                  <span className="font-mono font-medium text-text">264 tiles (held-out vessel sites)</span>
                </div>
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-text-muted">Test Evaluation Set:</span>
                  <span className="font-mono font-medium text-text">358 tiles (312 targets + 46 negatives)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-muted">Production Weights:</span>
                  <span className="font-mono font-medium text-primary">sagarnetra_real_yolov8n.pt &amp; .onnx</span>
                </div>
              </div>
            </div>
          </div>

          {/* Real Evaluation Metrics & Parity Card */}
          <div className="panel p-4 space-y-3">
            <div className="flex justify-between items-center">
              <div className="section-label">HELD-OUT TEST SPLIT EVALUATION &amp; PARITY</div>
              <span className="px-2 py-0.5 text-[11px] font-mono bg-primary/10 text-primary border border-primary/30 rounded font-semibold">
                STATUS: TRAINED_1_CLASS_WRECK
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-2.5 rounded bg-surface border border-border">
                <div className="text-[11px] text-text-muted">mAP@50 (Test)</div>
                <div className="text-[18px] font-mono font-bold text-text">0.0084</div>
                <div className="text-[10px] text-text-muted">358 test tiles</div>
              </div>
              <div className="p-2.5 rounded bg-surface border border-border">
                <div className="text-[11px] text-text-muted">Precision</div>
                <div className="text-[18px] font-mono font-bold text-text">4.3%</div>
                <div className="text-[10px] text-text-muted">mp = 0.0425</div>
              </div>
              <div className="p-2.5 rounded bg-surface border border-border">
                <div className="text-[11px] text-text-muted">Recall</div>
                <div className="text-[18px] font-mono font-bold text-text">5.1%</div>
                <div className="text-[10px] text-text-muted">mr = 0.0513</div>
              </div>
              <div className="p-2.5 rounded bg-surface border border-border">
                <div className="text-[11px] text-text-muted">ONNX Parity</div>
                <div className="text-[18px] font-mono font-bold text-success">PASSED</div>
                <div className="text-[10px] text-text-muted">max diff &lt; 1e-6</div>
              </div>
            </div>

            {/* Honest Disclaimer */}
            <div className="p-3 rounded bg-amber-500/10 border border-amber-500/30 text-[12px] text-amber-200">
              <span className="font-bold mr-1.5">[Rule G1 Note]:</span>
              Pipe, cylinder and net classes: training pending (limited real data). YOLO currently operates on single-class real shipwreck backscatter; other man-made and debris targets are detected and verified via EchoSift physics and PatchCore anomaly analysis.
            </div>
          </div>

          <div className="panel p-4 space-y-3">
            <div className="section-label">CORE ARCHITECTURAL STACK</div>
            <div className="space-y-2 text-[13px]">
              <div><b>Neural Backbone:</b> YOLOv8n lightweight CNN (72 layers, 3.01M parameters) trained directly on real acoustic waterfall tiles.</div>
              <div><b>Production Engine:</b> ONNX Runtime FP32 and INT8 TensorRT deployment profiles ready for onboard edge compute.</div>
              <div><b>Acoustic Physics Layer:</b> EchoSift verification suite executing pure NumPy/OpenCV geometric routines with &lt; 1.2ms latency overhead.</div>
              <div><b>Taxonomy Mapping:</b> Aligned with PS 26057: trained known class <code>wreck</code>. Decision routing: <code>unknown_manmade</code>, <code>natural_suppressed</code>, <code>uncertain</code>, <code>invalid_input</code>.</div>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Tests */}
      {subTab === "tests" && (
        <div className="space-y-4">
          <div className="pb-3 border-b border-border flex justify-between items-center">
            <div>
              <div className="section-label">AUTOMATED TEST SUITE EXECUTION</div>
              <h1 className="text-[20px] font-semibold text-text mt-0.5">
                Pytest Verification Results (97 Passed, 0 Failed)
              </h1>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-success/10 border border-success/30 rounded text-success font-mono text-[12px] font-bold">
              <CheckCircle2 className="w-4 h-4" />
              <span>100% PASS RATE</span>
            </div>
          </div>

          <div className="panel overflow-hidden">
            <table className="hydro-table">
              <thead>
                <tr>
                  <th>Test Module</th>
                  <th>Description</th>
                  <th>Tests Passed</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="font-mono font-bold">tests/test_echosift.py</td>
                  <td>SHC acoustic height formula, nadir direction, GRI, motion mask veto</td>
                  <td className="font-mono">5 / 5</td>
                  <td><span className="text-success font-mono font-bold">PASSED</span></td>
                </tr>
                <tr>
                  <td className="font-mono font-bold">tests/test_evidence_aware.py</td>
                  <td>Review actions, capability matrix honest degradation, coverage states</td>
                  <td className="font-mono">3 / 3</td>
                  <td><span className="text-success font-mono font-bold">PASSED</span></td>
                </tr>
                <tr>
                  <td className="font-mono font-bold">tests/test_no_fake_coordinates.py</td>
                  <td>Non-fabrication guarantee for image-only mode</td>
                  <td className="font-mono">1 / 1</td>
                  <td><span className="text-success font-mono font-bold">PASSED</span></td>
                </tr>
                <tr>
                  <td className="font-mono font-bold">tests/test_dataset_leakage.py</td>
                  <td>Zero geographic leakage between train and held-out test splits</td>
                  <td className="font-mono">2 / 2</td>
                  <td><span className="text-success font-mono font-bold">PASSED</span></td>
                </tr>
                <tr>
                  <td className="font-mono font-bold">tests/test_m0 to test_m10</td>
                  <td>Full scaffold, sonarforge, preprocess, detect, dataset, model, verifier, geo, api, demo</td>
                  <td className="font-mono">86 / 86</td>
                  <td><span className="text-success font-mono font-bold">PASSED</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
