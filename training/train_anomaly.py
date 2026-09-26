"""
SagarNetra Training — PatchCore-Lite Memory Bank Builder.
Extracts patch embeddings from nominal seabed tiles and builds the coreset memory bank.
Outputs:
  - Memory bank: artifacts/models/patchcore_bank.npz
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List

import numpy as np

from backend.sagarnetra.detect.anomaly import PatchCoreLite
from backend.sagarnetra.preprocess.despeckle import enhanced_lee_filter
from backend.sagarnetra.preprocess.features import generate_feature_stack
from sonarforge.seabed import PRESETS, SeabedGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def generate_nominal_seabed_tiles(
    num_tiles_per_preset: int = 2,
    tile_size: int = 512,
    seed: int = 42,
) -> List[np.ndarray]:
    """
    Generates synthetic seabed-only tiles without any objects or debris.
    """
    rng = np.random.default_rng(seed)
    nominal_stacks = []

    for preset_name in PRESETS.keys():
        for i in range(num_tiles_per_preset):
            width_m = tile_size * SeabedGenerator.RESOLUTION_M
            gen = SeabedGenerator(preset_name, seed=int(rng.integers(0, 1_000_000)))
            h_map, _ = gen.generate(width_m=width_m, length_m=width_m)
            h_crop = h_map[:tile_size, :tile_size]

            # Natural baseline backscatter + speckle
            bg = np.clip(0.35 + 0.15 * (h_crop - np.mean(h_crop)), 0.05, 0.85).astype(np.float32)
            speckle = rng.gamma(shape=4.0, scale=0.25, size=(tile_size, tile_size)).astype(np.float32)
            tile_raw = np.clip(bg * speckle, 0.0, 1.0)

            # Preprocessing
            despeckled = enhanced_lee_filter(tile_raw, window_size=7)
            feat_stack = generate_feature_stack(despeckled)
            nominal_stacks.append(feat_stack)

    logger.info("Generated %d nominal seabed feature stacks", len(nominal_stacks))
    return nominal_stacks


def train_patchcore_bank(
    output_dir: str | Path = "artifacts",
    num_nominal_tiles: int = 10,
    coreset_ratio: float = 0.08,
) -> Path:
    """
    Builds and saves the PatchCore memory bank.
    """
    output_dir = Path(output_dir)
    models_dir = output_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    save_path = models_dir / "patchcore_bank.npz"

    detector = PatchCoreLite()

    tiles_per_preset = max(1, num_nominal_tiles // len(PRESETS))
    nominal_tiles = generate_nominal_seabed_tiles(num_tiles_per_preset=tiles_per_preset)

    logger.info("Extracting patch embeddings and building coreset bank...")
    detector.build_memory_bank(nominal_tiles, coreset_ratio=coreset_ratio)

    detector.save_memory_bank(save_path)
    logger.info("Saved PatchCore memory bank to %s (Coreset size: %d)", save_path, len(detector.memory_bank))

    # Sanity check anomaly prediction on one nominal tile
    test_result = detector.predict_anomaly(nominal_tiles[0])
    logger.info(
        "Sanity test on nominal tile: score=%.3f, is_unknown=%s",
        test_result.anomaly_score,
        test_result.is_unknown_manmade,
    )

    return save_path


def main():
    parser = argparse.ArgumentParser(description="Build PatchCore-Lite Memory Bank")
    parser.add_argument("--output-dir", type=str, default="artifacts")
    parser.add_argument("--tiles", type=int, default=10)
    parser.add_argument("--coreset-ratio", type=float, default=0.08)
    args = parser.parse_args()

    train_patchcore_bank(
        output_dir=args.output_dir,
        num_nominal_tiles=args.tiles,
        coreset_ratio=args.coreset_ratio,
    )


if __name__ == "__main__":
    main()
