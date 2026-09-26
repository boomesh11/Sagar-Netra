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

## M5 — Dataset Builder & DATASET_CARD.md (NEXT)
**Status**: NEXT
- `sonarforge/inject.py`: Hybrid injector blending synthetic targets into real seabed backgrounds with matching geometry and K-distribution speckle
- `sonarforge/dataset_builder.py`: Builds Synthetic (S), Hybrid (H), and Real (R) dataset splits
- `DATASET_CARD.md`: Comprehensive dataset documentation with class counts, sources, and statistics
