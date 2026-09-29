"""
Phase 0 — Import Smoke Test.
Attempts to import every Python module in backend/sagarnetra and sonarforge.
Reports PASS / FAIL per module with the full exception on failure.
Exit code 0 only if all pass.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import sys

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULES = [
    # backend.sagarnetra
    "backend.sagarnetra",
    "backend.sagarnetra.api.app",
    "backend.sagarnetra.api.store",
    "backend.sagarnetra.change.disaster",
    "backend.sagarnetra.confidence",
    "backend.sagarnetra.confidence.calibrate",
    "backend.sagarnetra.confidence.fusion",
    "backend.sagarnetra.coverage.pod_map",
    "backend.sagarnetra.detect.cfar",
    "backend.sagarnetra.detect.fuse_candidates",
    "backend.sagarnetra.detect.net_signature",
    "backend.sagarnetra.detect.anomaly",
    "backend.sagarnetra.detect.yolo_onnx",
    "backend.sagarnetra.geo.dimensions",
    "backend.sagarnetra.geo.error_budget",
    "backend.sagarnetra.geo.project",
    "backend.sagarnetra.io.image_log_reader",
    "backend.sagarnetra.io.pipeline_schema",
    "backend.sagarnetra.io.schema",
    "backend.sagarnetra.io.snl",
    "backend.sagarnetra.io.xtf_reader",
    "backend.sagarnetra.io.xtf_writer",
    "backend.sagarnetra.preprocess.bottom_track",
    "backend.sagarnetra.preprocess.despeckle",
    "backend.sagarnetra.preprocess.features",
    "backend.sagarnetra.preprocess.gain",
    "backend.sagarnetra.preprocess.modality",
    "backend.sagarnetra.preprocess.motion",
    "backend.sagarnetra.preprocess.pipeline",
    "backend.sagarnetra.preprocess.quality",
    "backend.sagarnetra.preprocess.slant_range",
    "backend.sagarnetra.preprocess.tiler",
    "backend.sagarnetra.report.generator",
    "backend.sagarnetra.track",
    "backend.sagarnetra.track.associate",
    "backend.sagarnetra.verify.echosift",
    "backend.sagarnetra.verify.rules",
    # sonarforge
    "sonarforge",
    "sonarforge.dataset_builder",
    "sonarforge.inject",
    "sonarforge.materials",
    "sonarforge.nav",
    "sonarforge.objects",
    "sonarforge.render",
    "sonarforge.scenes",
    "sonarforge.seabed",
]

passed: list[str] = []
failed: list[tuple[str, str]] = []

for mod in MODULES:
    try:
        importlib.import_module(mod)
        passed.append(mod)
        print(f"PASS  {mod}")
    except Exception:
        tb = traceback.format_exc().strip()
        failed.append((mod, tb))
        print(f"FAIL  {mod}")
        print(f"      {tb.splitlines()[-1]}")

print()
print("=" * 60)
print(f"PASSED: {len(passed)}/{len(MODULES)}")
print(f"FAILED: {len(failed)}/{len(MODULES)}")

if failed:
    print()
    print("FAILED MODULE DETAILS:")
    for mod, tb in failed:
        print(f"\n--- {mod} ---")
        print(tb)
    sys.exit(1)
else:
    print("All imports succeeded.")
    sys.exit(0)
