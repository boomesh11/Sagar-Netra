"""
SonarForge objects — ghost nets, ropes, pipes, cylinders, wreck debris,
traps, and confusers (rocks, ripples, seagrass, fish schools).
Each object yields a height map delta, material map delta, and instance mask.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from sonarforge.materials import Material


@dataclass
class ObjectInstance:
    """A placed object in the scene."""
    class_name: str
    subtype: str = ""
    center_x_m: float = 0.0
    center_y_m: float = 0.0
    length_m: float = 1.0
    width_m: float = 0.5
    height_m: float = 0.3
    heading_deg: float = 0.0
    burial_frac: float = 0.0
    material: Material = Material.NYLON_TWINE
    # Ground-truth physical properties
    lat: Optional[float] = None
    lon: Optional[float] = None


def make_ghost_net(
    center_x_m: float,
    center_y_m: float,
    length_m: float = 10.0,
    width_m: float = 3.0,
    heading_deg: float = 45.0,
    burial_frac: float = 0.2,
    float_spacing_m: float = 1.0,
    mesh_period_m: float = 0.05,
    rng: Optional[np.random.Generator] = None,
) -> ObjectInstance:
    """Create a ghost net object specification."""
    if rng is None:
        rng = np.random.default_rng()
    height_m = rng.uniform(0.05, 1.5) * (1.0 - burial_frac)
    return ObjectInstance(
        class_name="ghost_net",
        center_x_m=center_x_m,
        center_y_m=center_y_m,
        length_m=length_m,
        width_m=width_m,
        height_m=max(0.05, height_m),
        heading_deg=heading_deg,
        burial_frac=burial_frac,
        material=Material.NYLON_TWINE,
    )


def make_pipe(
    center_x_m: float,
    center_y_m: float,
    length_m: float = 30.0,
    diameter_m: float = 0.5,
    heading_deg: float = 90.0,
    burial_frac: float = 0.1,
    rng: Optional[np.random.Generator] = None,
) -> ObjectInstance:
    return ObjectInstance(
        class_name="pipe",
        center_x_m=center_x_m,
        center_y_m=center_y_m,
        length_m=length_m,
        width_m=diameter_m,
        height_m=diameter_m * (1.0 - burial_frac),
        heading_deg=heading_deg,
        burial_frac=burial_frac,
        material=Material.METAL,
    )


def make_cylinder(
    center_x_m: float,
    center_y_m: float,
    diameter_m: float = 0.5,
    length_m: float = 1.5,
    heading_deg: float = 0.0,
    rng: Optional[np.random.Generator] = None,
) -> ObjectInstance:
    return ObjectInstance(
        class_name="cylinder",
        center_x_m=center_x_m,
        center_y_m=center_y_m,
        length_m=length_m,
        width_m=diameter_m,
        height_m=diameter_m,
        heading_deg=heading_deg,
        material=Material.METAL,
    )


def make_wreck_debris(
    center_x_m: float,
    center_y_m: float,
    length_m: float = 10.0,
    width_m: float = 4.0,
    height_m: float = 2.0,
    subtype: str = "boat",
    heading_deg: float = 0.0,
) -> ObjectInstance:
    return ObjectInstance(
        class_name="wreck_debris",
        subtype=subtype,
        center_x_m=center_x_m,
        center_y_m=center_y_m,
        length_m=length_m,
        width_m=width_m,
        height_m=height_m,
        heading_deg=heading_deg,
        material=Material.METAL,
    )


def make_trap_pot(
    center_x_m: float,
    center_y_m: float,
    size_m: float = 0.7,
) -> ObjectInstance:
    return ObjectInstance(
        class_name="trap_pot",
        center_x_m=center_x_m,
        center_y_m=center_y_m,
        length_m=size_m,
        width_m=size_m,
        height_m=size_m * 0.8,
        material=Material.METAL,
    )


def make_rope_cable(
    center_x_m: float,
    center_y_m: float,
    length_m: float = 20.0,
    diameter_m: float = 0.02,
    heading_deg: float = 30.0,
) -> ObjectInstance:
    return ObjectInstance(
        class_name="rope_cable",
        center_x_m=center_x_m,
        center_y_m=center_y_m,
        length_m=length_m,
        width_m=diameter_m,
        height_m=diameter_m,
        heading_deg=heading_deg,
        material=Material.NYLON_TWINE,
    )


def place_object_on_heightmap(
    height_map: np.ndarray,
    material_map: np.ndarray,
    obj: ObjectInstance,
    ground_res_m: float = 0.10,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Add an object to the height and material maps.
    Returns (updated_height_map, updated_material_map, instance_mask).
    """
    L, W = height_map.shape
    instance_mask = np.zeros((L, W), dtype=bool)

    # Convert object position to pixel coordinates
    cx_px = int(obj.center_x_m / ground_res_m)
    cy_px = int(obj.center_y_m / ground_res_m)
    l_px = max(1, int(obj.length_m / ground_res_m))
    w_px = max(1, int(obj.width_m / ground_res_m))
    h_m = obj.height_m

    mat_idx = list(Material).index(obj.material)

    # Create rotated bounding box
    angle_rad = np.deg2rad(obj.heading_deg)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)

    for dy in range(-w_px // 2, w_px // 2 + 1):
        for dx in range(-l_px // 2, l_px // 2 + 1):
            # Rotate
            rx = int(dx * cos_a - dy * sin_a) + cx_px
            ry = int(dx * sin_a + dy * cos_a) + cy_px
            if 0 <= rx < W and 0 <= ry < L:
                # Smooth height profile (elliptical cross-section)
                frac_l = abs(dx) / max(l_px // 2, 1)
                frac_w = abs(dy) / max(w_px // 2, 1)
                ellipse_factor = max(0.0, 1.0 - frac_l ** 2 - frac_w ** 2)
                dh = h_m * ellipse_factor * (1.0 - obj.burial_frac)
                if dh > 0:
                    height_map[ry, rx] += dh
                    material_map[ry, rx] = mat_idx
                    instance_mask[ry, rx] = True

    return height_map, material_map, instance_mask
