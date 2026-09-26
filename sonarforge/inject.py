"""
SonarForge Hybrid Injector.
Paints physically consistent synthetic debris (ghost nets, pipes, cylinders, wrecks, etc.)
into real or ambient seabed tiles with matching geometry, acoustic shadow projection,
noise floor attenuation, and K-distribution speckle blending.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
from scipy.ndimage import gaussian_filter

from sonarforge.materials import Material, get_props
from sonarforge.objects import ObjectInstance, place_object_on_heightmap
from sonarforge.render import compute_shadow_length_m


@dataclass
class HybridInjectionResult:
    blended_tile: np.ndarray           # Shape: [H, W], float32 image with injected object
    instance_mask: np.ndarray          # Shape: [H, W], boolean mask of injected object highlight
    shadow_mask: np.ndarray            # Shape: [H, W], boolean mask of cast acoustic shadow
    class_name: str                    # e.g. "ghost_net"
    ground_range_m: float              # Horizontal distance from nadir in meters
    altitude_m: float                  # Estimated towfish altitude
    shadow_length_m: float             # Physical shadow length in meters
    source: str = "hybrid"


def estimate_background_statistics(
    seabed_tile: np.ndarray,
) -> Tuple[float, float, float]:
    """
    Estimates ambient acoustic statistics of the seabed background:
    mean intensity, noise floor (5th percentile), and speckle variance.
    """
    mean_val = float(np.mean(seabed_tile))
    std_val = float(np.std(seabed_tile))
    noise_floor = float(np.percentile(seabed_tile, 5.0))
    return max(mean_val, 0.05), max(std_val, 0.01), max(noise_floor, 0.01)


def inject_object_into_seabed(
    seabed_tile: np.ndarray,
    obj: ObjectInstance,
    altitude_m: float = 6.0,
    nadir_col: int = 0,
    ground_res_m: float = 0.10,
    blend_margin_px: int = 3,
    rng: Optional[np.random.Generator] = None,
) -> HybridInjectionResult:
    """
    Injects a synthetic 3D object onto a seabed background tile.
    
    Physics:
    1. Object highlight: added with backscatter delta based on material acoustic properties.
    2. Acoustic shadow: cast in the range direction away from nadir (col > object_col if nadir_col == 0).
       Shadow length: L_s = (h * x_0) / (H - h).
    3. Shadow attenuation: the shadow zone is attenuated to the background noise floor.
    4. Speckle matching: speckle texture sampled to match the background distribution.
    5. Soft boundary blending: Poisson/linear edge feathering around highlight and shadow.
    
    Args:
        seabed_tile: [H, W] float32 array in [0, 1]
        obj: ObjectInstance specification
        altitude_m: towfish altitude in meters
        nadir_col: column index representing nadir (0 for starboard, W-1 for port)
        ground_res_m: pixel spatial resolution in meters (default 0.10 m)
        blend_margin_px: feathering radius for smooth edge transitions
        rng: optional random generator
        
    Returns:
        HybridInjectionResult with blended tile and ground truth masks.
    """
    if rng is None:
        rng = np.random.default_rng()

    h_img, w_img = seabed_tile.shape
    out_tile = seabed_tile.copy().astype(np.float32)

    bg_mean, bg_std, bg_noise_floor = estimate_background_statistics(seabed_tile)

    # Convert object location to pixel coordinates
    center_r_px = int(np.clip(obj.center_y_m / ground_res_m, 0, h_img - 1))
    center_c_px = int(np.clip(obj.center_x_m / ground_res_m, 0, w_img - 1))

    # Object dimensions in pixels
    l_px = max(2, int(obj.length_m / ground_res_m))
    w_px = max(2, int(obj.width_m / ground_res_m))
    h_m = max(0.05, float(obj.height_m) * (1.0 - obj.burial_frac))

    # Generate object highlight footprint
    highlight_mask = np.zeros((h_img, w_img), dtype=bool)
    height_profile = np.zeros((h_img, w_img), dtype=np.float32)

    angle_rad = np.deg2rad(obj.heading_deg)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)

    for dy in range(-w_px // 2, w_px // 2 + 1):
        for dx in range(-l_px // 2, l_px // 2 + 1):
            rx = int(dx * cos_a - dy * sin_a) + center_c_px
            ry = int(dx * sin_a + dy * cos_a) + center_r_px
            if 0 <= rx < w_img and 0 <= ry < h_img:
                frac_l = abs(dx) / max(l_px // 2, 1)
                frac_w = abs(dy) / max(w_px // 2, 1)
                ellipse_factor = max(0.0, 1.0 - (frac_l**2) - (frac_w**2))
                if ellipse_factor > 0:
                    highlight_mask[ry, rx] = True
                    height_profile[ry, rx] = h_m * np.sqrt(ellipse_factor)

    # Ground range of object center from nadir
    ground_range_m = max(abs(center_c_px - nadir_col) * ground_res_m, 1.0)

    # Physical acoustic shadow length: L_s = (h * x_0) / (H - h)
    shadow_len_m = compute_shadow_length_m(h_m, ground_range_m, altitude_m)
    shadow_len_px = max(1, int(round(shadow_len_m / ground_res_m)))

    # Direction of shadow: away from nadir
    shadow_dir = 1 if center_c_px >= nadir_col else -1

    # Project shadow mask
    shadow_mask = np.zeros((h_img, w_img), dtype=bool)
    hl_rows, hl_cols = np.where(highlight_mask)

    for r, c in zip(hl_rows, hl_cols):
        local_h = height_profile[r, c]
        if local_h <= 0.02:
            continue
        local_sh_len = int(round(compute_shadow_length_m(local_h, ground_range_m, altitude_m) / ground_res_m))
        for step in range(1, local_sh_len + 1):
            sh_c = c + shadow_dir * step
            if 0 <= sh_c < w_img:
                if not highlight_mask[r, sh_c]:
                    shadow_mask[r, sh_c] = True

    # 1. Apply Highlight with material backscatter boost
    mat_props = get_props(obj.material)
    # Relative backscatter boost in [0.15, 0.60] depending on material
    boost_map = {
        Material.METAL: 0.55,
        Material.ROCK: 0.45,
        Material.WOOD: 0.35,
        Material.AIR_FLOAT: 0.65,
        Material.FOAM_FLOAT: 0.40,
        Material.NYLON_TWINE: 0.25,
        Material.SEAGRASS: 0.20,
        Material.MUD: 0.10,
        Material.SAND: 0.15,
    }
    boost = boost_map.get(obj.material, 0.30)
    highlight_val = np.clip(bg_mean + boost, 0.0, 1.0)

    # Multiplicative speckle on highlight
    speckle_hl = rng.gamma(shape=mat_props.k_nu, scale=1.0 / mat_props.k_nu, size=(h_img, w_img))
    hl_textured = np.clip(highlight_val * speckle_hl, 0.0, 1.0)

    # 2. Apply Shadow attenuation
    # Shadow intensity drops down toward acoustic noise floor
    shadow_speckle = rng.gamma(shape=2.0, scale=0.5, size=(h_img, w_img))
    shadow_val = np.clip(bg_noise_floor * 0.7 * shadow_speckle, 0.0, 0.15)

    # 3. Soft blending (feathering edges)
    hl_feathered = gaussian_filter(highlight_mask.astype(np.float32), sigma=blend_margin_px / 2.0)
    sh_feathered = gaussian_filter(shadow_mask.astype(np.float32), sigma=blend_margin_px / 2.0)

    # Combine: base background -> attenuate shadow -> paint highlight
    out_tile = out_tile * (1.0 - sh_feathered) + shadow_val * sh_feathered
    out_tile = out_tile * (1.0 - hl_feathered) + hl_textured * hl_feathered

    return HybridInjectionResult(
        blended_tile=np.clip(out_tile, 0.0, 1.0).astype(np.float32),
        instance_mask=highlight_mask,
        shadow_mask=shadow_mask,
        class_name=obj.class_name,
        ground_range_m=ground_range_m,
        altitude_m=altitude_m,
        shadow_length_m=shadow_len_m,
        source="hybrid",
    )
