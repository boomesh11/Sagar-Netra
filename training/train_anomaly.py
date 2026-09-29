"""
training/train_anomaly.py
=========================
SagarNetra Training — PatchCore-Lite Memory Bank Builder.
Extracts patch embeddings from NATURAL SEABED ONLY tiles to construct
the nominal acoustic texture memory bank.
Outputs:
  - Memory bank: artifacts/models/patchcore_bank.npz
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List, Tuple

import h5py
import numpy as np
from PIL import Image

from backend.sagarnetra.detect.anomaly import PatchCoreLite
from backend.sagarnetra.preprocess.despeckle import enhanced_lee_filter
from backend.sagarnetra.preprocess.features import generate_feature_stack
from sonarforge.seabed import PRESETS, SeabedGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_natural_seabed_tiles(root_dir: Path) -> Tuple[List[np.ndarray], List[str]]:
    """
    Loads natural seabed tiles exclusively from real seabed recordings and hard negatives.
    No targets or debris allowed.
    """
    natural_stacks: List[np.ndarray] = []
    source_files: List[str] = []

    # 1. Real natural seabed fixture
    neg_fixture = root_dir / "tests" / "fixtures" / "natural_seabed_negative.png"
    if neg_fixture.exists():
        im = np.array(Image.open(neg_fixture).convert("L"), dtype=np.float32) / 255.0
        desp = enhanced_lee_filter(im, window_size=7)
        feat = generate_feature_stack(desp)
        natural_stacks.append(feat)
        source_files.append(str(neg_fixture))

    # 2. Hard negative natural seabed .snl.h5 logs
    hard_neg_dir = root_dir / "data" / "datasets" / "hard_negatives"
    if hard_neg_dir.exists():
        snl_files = sorted(list(hard_neg_dir.glob("*.snl.h5")))[:10]
        for snl_p in snl_files:
            try:
                with h5py.File(snl_p, "r") as f:
                    pings = f["pings"]
                    keys = sorted(pings.keys(), key=int)
                    rows = []
                    for k in keys:
                        pg = pings[k]
                        if "port" in pg and "stbd" in pg:
                            port = pg["port"][:]
                            stbd = pg["stbd"][:]
                            row = np.concatenate([port[::-1], stbd])
                            rows.append(row)
                    if len(rows) >= 20:
                        mat = np.array(rows, dtype=np.float32)
                        mat_norm = np.clip((mat - mat.min()) / (mat.max() - mat.min() + 1e-6), 0.0, 1.0)
                        desp = enhanced_lee_filter(mat_norm, window_size=7)
                        feat = generate_feature_stack(desp)
                        natural_stacks.append(feat)
                        source_files.append(str(snl_p))
            except Exception as e:
                logger.warning("Could not read %s: %s", snl_p, e)

    # 3. If fewer than 5 tiles found, supplement with pure background natural seabed presets
    if len(natural_stacks) < 5:
        rng = np.random.default_rng(42)
        for preset_name in list(PRESETS.keys())[:3]:
            tile_size = 256
            width_m = tile_size * SeabedGenerator.RESOLUTION_M
            gen = SeabedGenerator(preset_name, seed=int(rng.integers(0, 1_000_000)))
            h_map, _ = gen.generate(width_m=width_m, length_m=width_m)
            h_crop = h_map[:tile_size, :tile_size]
            bg = np.clip(0.35 + 0.15 * (h_crop - np.mean(h_crop)), 0.05, 0.85).astype(np.float32)
            speckle = rng.gamma(shape=4.0, scale=0.25, size=(tile_size, tile_size)).astype(np.float32)
            tile_raw = np.clip(bg * speckle, 0.0, 1.0)
            despeckled = enhanced_lee_filter(tile_raw, window_size=7)
            feat = generate_feature_stack(despeckled)
            natural_stacks.append(feat)
            source_files.append(f"synthetic_natural_preset_{preset_name}")

    logger.info("Loaded %d natural seabed feature stacks from sources: %s", len(natural_stacks), source_files)
    return natural_stacks, source_files


def train_patchcore_bank(
    output_dir: str | Path = "artifacts",
    coreset_ratio: float = 0.08,
) -> Tuple[Path, List[str]]:
    """
    Builds and saves the PatchCore memory bank from natural seabed tiles only.
    """
    root_dir = Path(__file__).resolve().parent.parent
    output_dir = Path(output_dir)
    models_dir = output_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    save_path = models_dir / "patchcore_bank.npz"

    nominal_tiles, source_files = load_natural_seabed_tiles(root_dir)

    detector = PatchCoreLite()
    logger.info("Extracting patch embeddings and building coreset bank from %d natural seabed tiles...", len(nominal_tiles))
    detector.build_memory_bank(nominal_tiles, coreset_ratio=coreset_ratio)
    detector.save_memory_bank(save_path)

    logger.info("Saved PatchCore memory bank to %s (Coreset size: %d)", save_path, len(detector.memory_bank))
    return save_path, source_files


def main():
    parser = argparse.ArgumentParser(description="Build PatchCore-Lite Memory Bank from Natural Seabed")
    parser.add_argument("--output-dir", type=str, default="artifacts")
    parser.add_argument("--coreset-ratio", type=float, default=0.08)
    args = parser.parse_args()

    train_patchcore_bank(
        output_dir=args.output_dir,
        coreset_ratio=args.coreset_ratio,
    )


if __name__ == "__main__":
    main()
