# SagarNetra Model Card: Sonar Multi-Head Segmentation & Anomaly Network
**Model Architecture:** `SagarNetraSegNet` + `PatchCoreLite`  
**Framework:** PyTorch 2.13 (TorchScript JIT Traced / ONNX Opset 17)  
**Date:** September 2026  
**License:** Apache 2.0  

---

## 1. Model Details

### Intended Use
- **Primary Use:** Automated detection, segmentation, and classification of marine debris, ghost fishing gear, and navigational hazards in side-scan sonar imagery.
- **Deployment Setting:** Completely offline onboard hydrographic and research vessels (NIOT, MoES, Indian Coast Guard, Indian Navy).
- **Inputs:** 3-channel Sonar Feature Stack ($512 \times 512$ float32 normalized):
  - **Ch 0:** Despeckled acoustic intensity (Enhanced Lee filtered).
  - **Ch 1:** Inverse-CFAR shadow extinction probability.
  - **Ch 2:** Sato continuous ridge eigenvalue map.
- **Outputs:**
  - Multi-class pixel segmentation masks ($512 \times 512 \times 10$).
  - Per-class classification logits (calibrated via temperature scaling).
  - Feature embedding distance for out-of-distribution anomaly scoring.

### Taxonomy
* **Target Hazard Classes:**
  1. `ghost_net` (Abandoned, lost, or discarded gillnets/trammel nets)
  2. `rope_cable` (Mooring hawsers, wire ropes, submarine cables)
  3. `pipe` (Exposed or displaced subsea pipelines)
  4. `cylinder` (Drums, barrels, mine-like cylindrical objects)
  5. `wreck_debris` (Sunken hulls, shipping containers, structural tetrapods)
  6. `trap_pot` (Crab/lobster traps and metallic cages)
* **Confuser Classes (Suppressed from final hazard reports):**
  7. `rock_cluster` (Natural boulders and reef outcroppings)
  8. `sand_ripple` (Acoustic seabed ripple patterns)
  9. `seagrass` (Marine flora meadows)
  10. `fish_school` (Water-column acoustic scatterers)

---

## 2. Performance & Calibration

### Core Metrics on Test Split
- **mAP50 (Hazard Classes):** PENDING_BENCHMARK (Evaluation run pending official benchmark)
- **Ghost Net Recall:** PENDING_BENCHMARK (Field validation strictly NOT_ESTABLISHED pending verified real data)
- **Uncalibrated ECE:** PENDING_BENCHMARK
- **Calibrated ECE:** PENDING_BENCHMARK
- **Brier Score (Calibrated):** PENDING_BENCHMARK

### Inference Latency
- **Laptop CPU (Intel Core i7, 1 thread):** Target: < 50 ms (pending field benchmark)
- **Edge GPU (Jetson Orin simulated):** Target: < 15 ms (pending field benchmark)

---

## 3. Training & Validation Data

- **Dataset:** `AI4Shipwrecks (NOAA EdgeTech 2205 SSS)` + registered open acoustic sets
- **Evaluation Split:** Held-out survey sites with strict survey/site isolation (zero spatial overlap)
- **Augmentation Constraints:** 
  - *Allowed:* Port/starboard mirror across nadir, along-track jitter, speckle re-sampling.
  - *Forbidden:* 90°/180° rotations or vertical flips (violates sonar grazing geometry and acoustic shadow orientation).

---

## 4. Ethical Considerations & Limitations
- **Dive Safety:** The model is not intended to replace human dive safety checklists. All high-confidence hazards include an honest $r_{95}$ error ellipse and require operator review before diver deployment.
- **Extreme Weather / High Sea State:** Excessive heave ($> 1.5\text{ m}$) or towfish roll ($> 10^\circ$) can degrade shadow resolution; in such cases, the system flags the survey track as `INSUFFICIENT_EVIDENCE`.
