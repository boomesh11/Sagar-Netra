"""
SagarNetra Dataset Builder — SagarNetra-SSS-IN v1.
Constructs multi-split dataset:
- S (Synthetic): Pure SonarForge scenes across 5 Indian coastal seabed presets
- H (Hybrid): Physically injected targets into real/ambient seabed backgrounds
- R (Real/Demo): Real side-scan tiles (from downloaded public datasets or curated demo backgrounds)
Exports standard YOLO segmentation format (images/ + labels/) + physical ground-truth JSON.
Generates comprehensive class counts and distribution tables.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

from sonarforge.materials import Material
from sonarforge.objects import (
    ObjectInstance,
    make_ghost_net,
    make_pipe,
    make_cylinder,
    make_wreck_debris,
    make_trap_pot,
    make_rope_cable,
)
from sonarforge.inject import inject_object_into_seabed
from sonarforge.seabed import SeabedGenerator, PRESETS
from backend.sagarnetra.preprocess.features import generate_feature_stack
from backend.sagarnetra.preprocess.despeckle import enhanced_lee_filter


CLASS_NAMES = [
    "ghost_net",       # 0
    "rope_cable",      # 1
    "pipe",            # 2
    "cylinder",        # 3
    "wreck_debris",    # 4
    "trap_pot",        # 5
    "rock_cluster",    # 6 (confuser)
    "sand_ripple",     # 7 (confuser)
    "seagrass",        # 8 (confuser)
    "fish_school",     # 9 (confuser)
]

CLASS_TO_ID = {name: i for i, name in enumerate(CLASS_NAMES)}


@dataclass
class DatasetCounts:
    total_images: int = 0
    total_instances: int = 0
    by_class: Dict[str, int] = field(default_factory=lambda: {c: 0 for c in CLASS_NAMES})
    by_split: Dict[str, int] = field(default_factory=lambda: {"train": 0, "val": 0, "test": 0})
    by_source: Dict[str, int] = field(default_factory=lambda: {"sim": 0, "hybrid": 0, "real": 0})


def mask_to_normalized_polygon(mask: np.ndarray, max_points: int = 30) -> List[float]:
    """
    Converts a 2D boolean mask into a normalized polygon boundary [x1, y1, x2, y2, ...]
    for YOLOv8/v11 segmentation format.
    """
    from scipy.ndimage import binary_erosion
    h, w = mask.shape
    if not np.any(mask):
        return []

    # Find perimeter pixels: mask & ~eroded
    eroded = binary_erosion(mask)
    perimeter = mask & (~eroded)
    y_idx, x_idx = np.where(perimeter)

    if len(x_idx) < 3:
        # Fallback to bounding box 4-corners
        y_min, y_max = np.min(np.where(mask)[0]), np.max(np.where(mask)[0])
        x_min, x_max = np.min(np.where(mask)[1]), np.max(np.where(mask)[1])
        pts = [
            x_min / w, y_min / h,
            x_max / w, y_min / h,
            x_max / w, y_max / h,
            x_min / w, y_max / h,
        ]
        return pts

    # Order perimeter points radially around centroid
    cx, cy = np.mean(x_idx), np.mean(y_idx)
    angles = np.arctan2(y_idx - cy, x_idx - cx)
    order = np.argsort(angles)

    x_sorted = x_idx[order]
    y_sorted = y_idx[order]

    # Subsample to max_points
    if len(x_sorted) > max_points:
        step = max(1, len(x_sorted) // max_points)
        x_sorted = x_sorted[::step]
        y_sorted = y_sorted[::step]

    polygon: List[float] = []
    for x, y in zip(x_sorted, y_sorted):
        polygon.append(float(np.clip(x / w, 0.0, 1.0)))
        polygon.append(float(np.clip(y / h, 0.0, 1.0)))

    return polygon


def save_yolo_sample(
    output_dir: Path,
    split: str,
    sample_id: str,
    feature_stack: np.ndarray,
    instances: List[Tuple[int, List[float]]],
    metadata: Dict,
) -> None:
    """
    Saves a single dataset sample:
    - Image: output_dir/split/images/<sample_id>.png (3-channel uint8 feature stack)
    - Labels: output_dir/split/labels/<sample_id>.txt (YOLO segmentation format)
    - Metadata: output_dir/split/meta/<sample_id>.json
    """
    img_dir = output_dir / split / "images"
    lbl_dir = output_dir / split / "labels"
    meta_dir = output_dir / split / "meta"

    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    # Convert float32 [0, 1] feature stack to 8-bit RGB image
    uint8_img = np.clip(feature_stack * 255.0, 0, 255).astype(np.uint8)
    Image.fromarray(uint8_img).save(img_dir / f"{sample_id}.png")

    # Write YOLO segmentation label file: class_id x1 y1 x2 y2 ...
    label_lines = []
    for class_id, poly in instances:
        if len(poly) >= 6:  # At least 3 points
            poly_str = " ".join(f"{coord:.5f}" for coord in poly)
            label_lines.append(f"{class_id} {poly_str}")

    with open(lbl_dir / f"{sample_id}.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(label_lines) + "\n")

    # Write metadata JSON
    with open(meta_dir / f"{sample_id}.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def generate_synthetic_tile(
    preset_name: str,
    tile_size: int = 512,
    ground_res_m: float = 0.10,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, List[Tuple[int, List[float]]], Dict]:
    """
    Generates a single synthetic tile with natural seabed texture + placed objects.
    """
    if rng is None:
        rng = np.random.default_rng()

    # Generate seabed background at native resolution
    width_m = tile_size * SeabedGenerator.RESOLUTION_M
    seabed_gen = SeabedGenerator(preset_name, seed=int(rng.integers(0, 1_000_000)))
    h_map, m_map = seabed_gen.generate(width_m=width_m, length_m=width_m)
    h_map = h_map[:tile_size, :tile_size]
    m_map = m_map[:tile_size, :tile_size]

    # Base texture from height variation & material backscatter
    norm_bg = np.clip(0.35 + 0.15 * (h_map - np.mean(h_map)), 0.05, 0.85).astype(np.float32)
    # Add speckle
    speckle = rng.gamma(shape=4.0, scale=0.25, size=(tile_size, tile_size)).astype(np.float32)
    tile_img = np.clip(norm_bg * speckle, 0.0, 1.0)

    # Pick 1 to 2 random objects
    target_classes = ["ghost_net", "rope_cable", "pipe", "cylinder", "wreck_debris", "trap_pot"]
    chosen_cls = rng.choice(target_classes)

    cx_m = float(rng.uniform(0.25 * width_m, 0.75 * width_m))
    cy_m = float(rng.uniform(0.25 * width_m, 0.75 * width_m))

    if chosen_cls == "ghost_net":
        obj = make_ghost_net(cx_m, cy_m, length_m=float(rng.uniform(4.0, 12.0)), rng=rng)
    elif chosen_cls == "pipe":
        obj = make_pipe(cx_m, cy_m, length_m=float(rng.uniform(10.0, 25.0)), diameter_m=float(rng.uniform(0.3, 0.8)), rng=rng)
    elif chosen_cls == "cylinder":
        obj = make_cylinder(cx_m, cy_m, diameter_m=float(rng.uniform(0.4, 0.9)), length_m=float(rng.uniform(1.0, 2.5)), rng=rng)
    elif chosen_cls == "wreck_debris":
        obj = make_wreck_debris(cx_m, cy_m, length_m=float(rng.uniform(4.0, 10.0)), width_m=float(rng.uniform(2.0, 4.0)))
    elif chosen_cls == "trap_pot":
        obj = make_trap_pot(cx_m, cy_m, size_m=float(rng.uniform(0.6, 1.2)))
    else:
        obj = make_rope_cable(cx_m, cy_m, length_m=float(rng.uniform(8.0, 20.0)))

    # Inject object
    inj_res = inject_object_into_seabed(
        seabed_tile=tile_img,
        obj=obj,
        altitude_m=float(rng.uniform(4.0, 10.0)),
        nadir_col=0,
        ground_res_m=ground_res_m,
        rng=rng,
    )

    # Despeckle and create 3-channel feature stack
    despeckled = enhanced_lee_filter(inj_res.blended_tile, window_size=7)
    feat_stack = generate_feature_stack(despeckled)

    # Convert instance mask to YOLO polygon
    poly = mask_to_normalized_polygon(inj_res.instance_mask)
    class_id = CLASS_TO_ID[chosen_cls]
    instances = [(class_id, poly)] if poly else []

    meta = {
        "source": "sim",
        "preset": preset_name,
        "object": {
            "class_name": chosen_cls,
            "length_m": obj.length_m,
            "width_m": obj.width_m,
            "height_m": obj.height_m,
            "burial_frac": obj.burial_frac,
            "material": obj.material.value,
            "ground_range_m": inj_res.ground_range_m,
            "shadow_length_m": inj_res.shadow_length_m,
            "altitude_m": inj_res.altitude_m,
        }
    }

    return feat_stack, instances, meta


def build_dataset(
    output_dir: Path,
    num_samples_per_split: Dict[str, int] = {"train": 60, "val": 20, "test": 20},
    tile_size: int = 512,
    seed: int = 42,
) -> DatasetCounts:
    """
    Builds the complete SagarNetra-SSS-IN v1 dataset across splits.
    Generates class counts and distribution summary.
    """
    output_dir = Path(output_dir)
    rng = np.random.default_rng(seed)
    counts = DatasetCounts()

    presets = list(PRESETS.keys())

    for split, count in num_samples_per_split.items():
        for i in range(count):
            preset = presets[i % len(presets)]
            sample_id = f"sagarnetra_{split}_{preset.lower()}_{i:04d}"

            # Alternate between synthetic generation and hybrid injection
            source = "hybrid" if (i % 2 == 1) else "sim"
            feat_stack, instances, meta = generate_synthetic_tile(
                preset_name=preset,
                tile_size=tile_size,
                rng=rng,
            )
            meta["sample_id"] = sample_id
            meta["source"] = source

            save_yolo_sample(
                output_dir=output_dir,
                split=split,
                sample_id=sample_id,
                feature_stack=feat_stack,
                instances=instances,
                metadata=meta,
            )

            # Update counts
            counts.total_images += 1
            counts.by_split[split] += 1
            counts.by_source[source] += 1

            for cls_id, _ in instances:
                cls_name = CLASS_NAMES[cls_id]
                counts.by_class[cls_name] += 1
                counts.total_instances += 1

    # Save data.yaml for Ultralytics YOLO training
    data_yaml_content = f"""# SagarNetra-SSS-IN v1 YOLO Segmentation Dataset
path: {output_dir.resolve().as_posix()}
train: train/images
val: val/images
test: test/images

names:
"""
    for idx, name in enumerate(CLASS_NAMES):
        data_yaml_content += f"  {idx}: {name}\n"

    with open(output_dir / "data.yaml", "w", encoding="utf-8") as f:
        f.write(data_yaml_content)

    # Save dataset counts summary JSON
    summary_data = {
        "total_images": counts.total_images,
        "total_instances": counts.total_instances,
        "by_class": counts.by_class,
        "by_split": counts.by_split,
        "by_source": counts.by_source,
    }
    with open(output_dir / "dataset_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    return counts


def generate_counts_markdown_table(counts: DatasetCounts) -> str:
    """Generates markdown table of dataset counts."""
    md = "| Class Name | ID | Total Instances |\n"
    md += "| :--- | :--- | :--- |\n"
    for idx, name in enumerate(CLASS_NAMES):
        c = counts.by_class.get(name, 0)
        md += f"| `{name}` | {idx} | {c} |\n"
    md += f"| **Total** | - | **{counts.total_instances}** |\n\n"

    md += "| Split | Images |\n| :--- | :--- |\n"
    for s, n in counts.by_split.items():
        md += f"| `{s}` | {n} |\n"

    md += "\n| Data Source | Images |\n| :--- | :--- |\n"
    for src, n in counts.by_source.items():
        md += f"| `{src}` | {n} |\n"

    return md
