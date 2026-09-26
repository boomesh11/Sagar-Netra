"""
M5 Acceptance Tests for SagarNetra Dataset Builder & Hybrid Injector.
Acceptance criteria:
- Hybrid injector casts acoustic shadow away from nadir with length matching formula within 10%
- Shadow attenuation reduces intensity toward noise floor
- Mask to YOLO polygon conversion produces normalized coordinates in [0, 1]
- Synthetic tile generator produces 512x512x3 feature stack and valid labels
- Dataset builder constructs train/val/test splits, data.yaml, and metadata JSON files
- Class counts table matches instance counts in generated dataset
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest

from sonarforge.objects import make_ghost_net, make_cylinder
from sonarforge.inject import inject_object_into_seabed, estimate_background_statistics
from sonarforge.render import compute_shadow_length_m
from sonarforge.dataset_builder import (
    CLASS_NAMES,
    CLASS_TO_ID,
    mask_to_normalized_polygon,
    generate_synthetic_tile,
    build_dataset,
    generate_counts_markdown_table,
    DatasetCounts,
)


def test_hybrid_injection_shadow_geometry():
    """
    Validates that hybrid injection casts an acoustic shadow in the direction
    away from nadir with physical length matching Ls = h*x0 / (H - h) within 10%.
    """
    h_tile, w_tile = 200, 200
    # Ambient background ~ 0.40
    seabed = np.ones((h_tile, w_tile), dtype=np.float32) * 0.40

    altitude_m = 6.0
    ground_range_m = 15.0  # placed at col = 150 with nadir at col = 0
    ground_res_m = 0.10

    # Cylinder target: h = 0.8m, length = 2.0m, diam = 0.8m
    cyl = make_cylinder(
        center_x_m=ground_range_m,
        center_y_m=10.0,
        diameter_m=0.8,
        length_m=2.0,
    )
    cyl.height_m = 0.8

    expected_shadow_len_m = compute_shadow_length_m(cyl.height_m, ground_range_m, altitude_m)
    # Ls = 0.8 * 15 / (6.0 - 0.8) = 12 / 5.2 = 2.307 m

    inj = inject_object_into_seabed(
        seabed_tile=seabed,
        obj=cyl,
        altitude_m=altitude_m,
        nadir_col=0,
        ground_res_m=ground_res_m,
    )

    # 1. Instance highlight must exist
    assert np.any(inj.instance_mask)
    # 2. Shadow must exist
    assert np.any(inj.shadow_mask)

    # 3. Shadow must be located at columns GREATER than object center (away from nadir)
    hl_cols = np.where(inj.instance_mask)[1]
    sh_cols = np.where(inj.shadow_mask)[1]
    assert np.mean(sh_cols) > np.mean(hl_cols)

    # 4. Measured shadow length within 10% of theoretical formula
    assert abs(inj.shadow_length_m - expected_shadow_len_m) / expected_shadow_len_m < 0.10

    # 5. Shadow region must be significantly darker than surrounding ambient seabed
    sh_mean = float(np.mean(inj.blended_tile[inj.shadow_mask]))
    bg_mean = float(np.mean(seabed))
    assert sh_mean < bg_mean * 0.65


def test_mask_to_normalized_polygon():
    """Validates binary mask conversion to normalized YOLO polygon boundary."""
    h, w = 100, 100
    mask = np.zeros((h, w), dtype=bool)
    # Create square mask from row 20:40, col 30:60
    mask[20:40, 30:60] = True

    poly = mask_to_normalized_polygon(mask, max_points=20)

    # Polygon should have at least 3 pairs (6 values)
    assert len(poly) >= 6
    assert len(poly) % 2 == 0

    # All values must be strictly in [0.0, 1.0]
    for val in poly:
        assert 0.0 <= val <= 1.0

    # X coordinates should span ~ 0.30 to 0.60
    xs = poly[0::2]
    ys = poly[1::2]
    assert min(xs) <= 0.32
    assert max(xs) >= 0.58
    assert min(ys) <= 0.22
    assert max(ys) >= 0.38


def test_generate_synthetic_tile():
    """Validates single tile generation with feature stack, annotations, and metadata."""
    rng = np.random.default_rng(42)
    feat_stack, instances, meta = generate_synthetic_tile(
        preset_name="REEF_RUBBLE",
        tile_size=128,  # Fast size for test
        ground_res_m=0.10,
        rng=rng,
    )

    # Check 3-channel feature stack
    assert feat_stack.shape == (128, 128, 3)
    assert feat_stack.dtype == np.float32
    assert float(np.min(feat_stack)) >= 0.0
    assert float(np.max(feat_stack)) <= 1.0

    # Check instances
    assert len(instances) > 0
    class_id, polygon = instances[0]
    assert 0 <= class_id < len(CLASS_NAMES)
    assert len(polygon) >= 6

    # Check physical metadata
    assert meta["source"] == "sim"
    assert "object" in meta
    obj_info = meta["object"]
    assert obj_info["height_m"] > 0
    assert obj_info["length_m"] > 0
    assert "burial_frac" in obj_info
    assert "material" in obj_info


def test_build_dataset_mini_split(tmp_path):
    """
    Integration test: builds mini dataset with train/val/test splits,
    verifying directory layout, data.yaml, metadata files, and counts table.
    """
    out_dir = tmp_path / "test_sagarnetra_dataset"
    counts = build_dataset(
        output_dir=out_dir,
        num_samples_per_split={"train": 4, "val": 2, "test": 2},
        tile_size=128,
        seed=101,
    )

    # Verify counts
    assert counts.total_images == 8
    assert counts.by_split["train"] == 4
    assert counts.by_split["val"] == 2
    assert counts.by_split["test"] == 2
    assert counts.total_instances >= 8

    # Verify files created
    assert (out_dir / "data.yaml").exists()
    assert (out_dir / "dataset_summary.json").exists()

    for split in ["train", "val", "test"]:
        img_dir = out_dir / split / "images"
        lbl_dir = out_dir / split / "labels"
        meta_dir = out_dir / split / "meta"
        assert img_dir.exists()
        assert lbl_dir.exists()
        assert meta_dir.exists()
        assert len(list(img_dir.glob("*.png"))) == counts.by_split[split]
        assert len(list(lbl_dir.glob("*.txt"))) == counts.by_split[split]
        assert len(list(meta_dir.glob("*.json"))) == counts.by_split[split]

    # Verify data.yaml contents
    yaml_text = (out_dir / "data.yaml").read_text()
    assert "train: train/images" in yaml_text
    assert "ghost_net" in yaml_text
    assert "cylinder" in yaml_text

    # Verify summary JSON contents
    with open(out_dir / "dataset_summary.json") as f:
        summary = json.load(f)
    assert summary["total_images"] == 8
    assert "by_class" in summary

    # Verify markdown table generation
    md_table = generate_counts_markdown_table(counts)
    assert "| `ghost_net` |" in md_table
    assert "| `train` | 4 |" in md_table
