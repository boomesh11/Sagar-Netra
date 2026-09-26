# SagarNetra Build Progress

## M0 — Repository Scaffold ✅
**Date**: 2026-09-26  
**Status**: COMPLETE (3/3 tests passed)  
**Acceptance**: Repo structure created, Makefile, Docker Compose, GitHub Actions CI, pyproject.toml, .gitignore, all package `__init__.py` files.

---

## M1 — Data Contracts & IO Layer ✅
**Date**: 2026-09-26  
**Status**: COMPLETE (7/7 tests passed)  
**Acceptance**:
- Pydantic v2 data contracts for Ping, Survey, Tile, Detection, ConfidenceComponents, Position, Dimensions
- XTF reader (`xtf_reader.py`) with pyxtf and fallback parser
- XTF writer (`xtf_writer.py`) producing real binary XTF files (XTFFILEHEADER, XTFPINGHEADER, XTFPINGCHANHEADER)
- SNL reader/writer (`snl.py`) HDF5 format with metadata and roundtrip preservation
- Image-log reader (`image_log_reader.py`) for waterfall images + sidecar navigation CSV

---

## M2 — SonarForge Physics Simulator ✅
**Date**: 2026-09-26  
**Status**: COMPLETE (10/10 tests passed)  
**Acceptance**:
- Acoustic materials table (`materials.py`) with Blondel & Lurton backscatter coefficients (dB) and K-distribution shape parameters
- 2.5D Seabed generator (`seabed.py`) with 5 Indian coastal presets (East Coast Sand, West Coast Mud, Reef Rubble, Seagrass Bed, Harbour Floor)
- Ray-casting sonar renderer (`render.py`) with Lambert backscatter, transmission loss, TVG, K-distribution speckle, shadow casting, and nadir gap
- Debris object models (`objects.py`): ghost nets (with headrope/footrope, floats, sinkers, mesh), pipes, cylinders, wrecks, traps, ropes, and confusers (rocks, ripples, seagrass)
- Lawnmower survey navigation (`nav.py`) around 6 Indian demo sites (Chennai, Kochi, Visakhapatnam, Gulf of Mannar, JNPT Mumbai, Paradip)
- Full scene generator (`scenes.py`) producing pings + ground truth labels + genuine XTF files

---

## M3 — Preprocessing & Signal Conditioning Chain ✅
**Date**: 2026-09-26  
**Status**: COMPLETE (9/9 tests passed)  
**Acceptance**:
- Quality and noise flagging (`quality.py`): dropouts, altitude jumps, nav gaps, excessive attitude rates; single dropout interpolation and multi-ping burst NO_DATA marking
- Bottom tracking (`bottom_track.py`): acoustic first-return gradient detection and Kalman-smoothed altitude estimator with header cross-check
- Slant-range correction (`slant_range.py`): water column removal and horizontal ground range resampling ($x = \sqrt{r^2 - H^2}$) strictly within 1 pixel (0.10 m) of synthetic truth
- Motion compensation (`motion.py`): along-track distance resampling by speed over ground, yaw compensation (crab angle shear), and heave correction
- Empirical gain normalisation (`gain.py`): sliding window mean across-track profile correction and dynamic range log-scaling $[0, 1]$
- Despeckle filter (`despeckle.py`): 7x7 Enhanced Lee filter reducing speckle variance in homogeneous seabed while preserving sharp target highlights and shadow edges
- Feature stack generator (`features.py`): 3-channel physics tensor (Ch0: intensity, Ch1: shadow probability, Ch2: Sato multi-scale ridge filter)
- Tiler (`tiler.py`): 512x512 windows with 25% overlap (stride 384 px) with spatial coordinate maps
- Master pipeline (`pipeline.py`): end-to-end `preprocess_survey_pings`

---

## M4 — CFAR Candidate Detection & Net Signature Head ✅
**Date**: 2026-09-26  
**Status**: COMPLETE (9/9 tests passed, 38/38 total)  
**Acceptance**:
- 2D OS-CFAR detector (`cfar.py`): highlights, acoustic shadows, and directional far-range highlight-shadow pairing with shadow length estimation and anti-causal rejection
- Net Signature Head (`net_signature.py`): multi-scale Hessian determinant float/sinker blob detector, MST chain regularity scoring (CV < 0.35), continuous rope ridge length, Gabor mesh texture energy, and human-readable evidence strings
- Candidate fusion & NMS (`fuse_candidates.py`): merges CFAR and Net Signature candidates with IoU-based Non-Maximum Suppression
- Evaluation on simulated scenes: PR curve evaluation on SonarForge synthetic scenes with full pipeline verification

---

## M5 — Dataset Builder & DATASET_CARD.md ✅
**Date**: 2026-09-26  
**Status**: COMPLETE (4/4 tests passed, 42/42 total)  
**Acceptance**:
- Hybrid injector (`sonarforge/inject.py`): paints physically consistent synthetic debris into real/ambient seabed backgrounds with acoustic shadow projection ($L_s = \frac{h \cdot x_0}{H - h}$), noise floor attenuation, and K-speckle matching
- Dataset builder (`sonarforge/dataset_builder.py`): builds Synthetic ($S$) and Hybrid ($H$) dataset splits, exports 3-channel feature stack tiles ($512\times 512$), YOLO polygon segmentation annotations, and sidecar physical metadata JSON
- Generated official dataset `sagarnetra_v1` (60 train, 20 val, 20 test; 100 images, 50 sim / 50 hybrid)
- `DATASET_CARD.md`: comprehensive benchmark dataset documentation with class counts table, Indian coastal presets, ontology, and license
- Acceptance tests: `tests/test_m5_dataset.py` (4/4 passed)

---

## M6 — YOLO Training, ONNX/TorchScript Export & Anomaly Head ✅
**Date**: 2026-09-26  
**Status**: COMPLETE (7/7 tests passed, 49/49 total)  
**Acceptance**:
- Stage B Sonar Segmentation Network (`backend/sagarnetra/detect/yolo_onnx.py`): `SagarNetraSegNet` lightweight architecture tailored to 3-channel physics feature stack (16 -> 32 -> 64 -> 128 channels, skip connections, dual mask + class heads) with < 20 ms CPU latency
- `SonarDetector` inference runner with automatic device placement, post-processing, and connected component polygon/bbox extraction
- PatchCore-Lite anomaly head (`backend/sagarnetra/detect/anomaly.py`): multi-scale patch embeddings, coreset memory bank from nominal Indian seabed tiles, and kNN distance anomaly scoring to detect post-cyclone unknown man-made debris
- Training pipelines (`training/train_yolo.py`, `training/train_anomaly.py`, `training/export_onnx.py`):
  - Model weights saved: `artifacts/models/sagarnetra_seg_quick.pt`
  - PatchCore bank saved: `artifacts/models/patchcore_bank.npz` (1,024 coreset embeddings)
  - Compiled TorchScript saved: `artifacts/models/sagarnetra_seg.torchscript`
  - Parity verification verified: $|\max \text{diff}| = 0.000000$ (exact bitwise parity between eager PyTorch and compiled execution)
  - Model metrics saved: `artifacts/metrics/m6_model_metrics.json`
- Acceptance tests: `tests/test_m6_model.py` (7/7 passed, 49/49 total)

---

## M7 — Physics Verifier & Calibrated Confidence Fusion ✅
**Date**: 2026-09-26  
**Status**: COMPLETE (7/7 tests passed, 56/56 total)  
**Acceptance**:
- Eight-rule Acoustic Physics Verifier (`backend/sagarnetra/verify/rules.py`):
  - $R_1$: Class height prior evaluation (net $0\text{--}1.5\text{ m}$, rope $0\text{--}0.35\text{ m}$, pipe $0.08\text{--}1.5\text{ m}$, cylinder $0.15\text{--}2.0\text{ m}$, wreck $0.4\text{--}15.0\text{ m}$, trap $0.2\text{--}1.3\text{ m}$)
  - $R_2$: Causal highlight-before-shadow ray order with anti-causal depression rejection
  - $R_3$: Port/starboard symmetric crosstalk mirror echo rejection
  - $R_4$: Along-track beam persistence check (minimum 2 consecutive pings; rejects transient noise)
  - $R_5$: Water column pre-bottom echo rejection ($r < 0.95 \cdot H$)
  - $R_6$: Nadir blind zone ($x < 1.0\text{ m}$) and surface bounce multipath rejection ($r \approx 2H$)
  - $R_7$: Beam footprint resolution adequacy ($\text{extent} \ge 2.5 \cdot F_h$)
  - $R_8$: Local seabed slope planar geometry validity ($\text{slope} \le 5^\circ$)
  - Calculates physical target height from acoustic shadow geometry: $h = \frac{H \cdot L_s}{x_0 + L_s}$
- Temperature Scaling Calibration (`backend/sagarnetra/confidence/calibrate.py`):
  - Optimizer tunes temperature parameter $T > 0$ on validation logits via negative log-likelihood
  - Expected Calibration Error (ECE) and Maximum Calibration Error (MCE) evaluated across 10 confidence bins
  - Generated reliability diagram saved to `artifacts/plots/reliability_diagram.png`
  - Calibration parameters saved to `artifacts/models/temperature_calibration.json`
  - Calibration metrics saved to `artifacts/metrics/m7_calibration_metrics.json`
- Calibrated Hazard Confidence Fusion (`backend/sagarnetra/confidence/fusion.py`):
  - Unified confidence formula:
    $$C = 100 \cdot \text{sigmoid}\left(w_0 + w_{\text{cal}}\text{logit}(p_{\text{cal}}) + w_{\text{obs}}Q_{\text{obs}} + w_{\text{phys}}V_{\text{phys}} + w_{\text{net}}S_{\text{net}} + w_{\text{views}}\min(\text{views}, 3)\right)$$
  - Four-tier honest operational triage: `CONFIRMED_HAZARD` ($C \ge 60\%$), `SUSPECTED_HAZARD` ($35\% \le C < 60\%$), `CONFUSER_REJECTED`, and `INSUFFICIENT_EVIDENCE`
  - Operational priority ranking with position error attenuation $\frac{1}{1 + r_{95}/10}$ and sensitive shipping channel/reef multiplier ($\times 1.5$)
- Acceptance tests: `tests/test_m7_verifier.py` (7/7 passed, 56/56 total)

---

## M8 — Geotagging, Dimensions, Coverage/PoD Clearance Map & Disaster Mode (NEXT)
**Status**: NEXT
- `backend/sagarnetra/geo/project.py`: GPS to UTM projection (zones 43N, 44N, 45N for Indian coastline), layback calculation ($L = \sqrt{C_{\text{out}}^2 - D_{\text{tow}}^2}$), towfish position interpolation, across-track offset to WGS84 latitude/longitude
- `backend/sagarnetra/geo/error_budget.py`: Full 5-component error budget ($\sigma_{\text{gps}}, \sigma_L, \sigma_\theta, \sigma_x, \sigma_t$) with 95% circular error probable radius $r_{95} = 2.45 \cdot \sigma_{\text{tot}}$
- `backend/sagarnetra/geo/dimensions.py`: Oriented minimum bounding box on ground-range mask computing physical length, width, orientation, footprint area, and height
- `backend/sagarnetra/track/associate.py`: Multi-view detection association across survey lines using overlapping error ellipses
- `backend/sagarnetra/coverage/pod_map.py`: Grid clearance map computing cell-by-cell Probability of Detection (PoD) for reference net and cylinder targets, clearance states (`SURVEYED_CLEAR`, `INSUFFICIENT`, `NOT_SURVEYED`, `CANDIDATE`), and second-look orthogonal line generator
- `backend/sagarnetra/change/disaster.py`: Pre/post-cyclone survey registration, log-ratio intensity comparison, and `NEW_OBSTRUCTION` change detection for Indian ports


