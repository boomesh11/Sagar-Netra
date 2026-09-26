"""
SonarForge renderer — the heart of the physics simulator.
Converts a 2.5D seabed height + material map into a side-scan sonar waterfall
using the sonar equation with ray casting.

Physics:
  I_dB = SL - 2*TL(r) + BS(theta_inc, material) + noise
  TL(r) = 20*log10(r) + alpha*r
  BS = mu_material + 10*log10(cos^2(theta_inc))  [Lambert]

Shadow: occlusion = noise floor only.
K-distribution speckle, TVG, nadir gap, multipath.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from sonarforge.materials import Material, MaterialProps, get_props, MATERIAL_TABLE


@dataclass
class SonarGeometry:
    altitude_m: float = 5.0
    range_m: float = 50.0
    frequency_hz: float = 450_000.0
    sound_speed_mps: float = 1500.0
    source_level_db: float = 220.0
    h_beamwidth_deg: float = 0.4  # 450 kHz typical
    tow_speed_mps: float = 2.0

    @property
    def alpha_db_per_m(self) -> float:
        """Frequency-dependent absorption (Francois-Garrison approximate)."""
        f_khz = self.frequency_hz / 1000.0
        return 0.0022 * f_khz ** 1.5 / 1000.0  # dB/m

    @property
    def sample_interval_s(self) -> float:
        return 1.0 / (2 * self.range_m * self.sound_speed_mps / (self.sound_speed_mps))

    @property
    def num_samples(self) -> int:
        return int(2 * self.range_m / self.sound_speed_mps / (1.0 / (self.sound_speed_mps / (2 * self.range_m) * 512)))


def _transmission_loss(r: np.ndarray, alpha_db_m: float) -> np.ndarray:
    """Two-way transmission loss in dB."""
    r_safe = np.maximum(r, 0.01)
    return 20.0 * np.log10(r_safe) + alpha_db_m * r_safe


def _lambert_bs(theta_inc_rad: np.ndarray, mu_db: float) -> np.ndarray:
    """Lambert backscatter strength in dB."""
    cos2 = np.cos(theta_inc_rad) ** 2
    cos2 = np.maximum(cos2, 1e-6)
    return mu_db + 10.0 * np.log10(cos2)


def _k_speckle(shape: float, size: int, rng: np.random.Generator) -> np.ndarray:
    """
    K-distributed multiplicative speckle.
    K(nu, mu=1): mean=1, variance=1/nu + 1 approximately.
    Large nu → Rayleigh (standard sonar speckle).
    Small nu → heavy-tailed (rough seafloor).
    """
    # K = Gamma(nu) * Rayleigh; approximate with sqrt(Gamma * chi2)
    gamma = rng.gamma(shape, 1.0 / shape, size)
    rayleigh = rng.rayleigh(1.0, size)
    speckle = gamma * rayleigh
    # Normalise so mean ≈ 1
    speckle /= (speckle.mean() + 1e-9)
    return speckle


def render_ping(
    height_profile: np.ndarray,  # [W] height at each ground-range bin (m)
    material_profile: np.ndarray,  # [W] material index
    geom: SonarGeometry,
    rng: np.random.Generator,
    ground_res_m: float = 0.10,
    noise_floor_db: float = -60.0,
    add_tvg: bool = True,
) -> np.ndarray:
    """
    Render one sonar ping (one side) from a height + material profile.

    Returns: uint16 array [N_samples] representing echo amplitude.
    """
    n_samples = int(geom.range_m / ground_res_m)
    W = len(height_profile)
    alpha = geom.alpha_db_per_m

    # Ground ranges corresponding to each sample
    x_samples = np.linspace(0, geom.range_m, n_samples)

    # Slant ranges
    H = geom.altitude_m
    r_samples = np.sqrt(x_samples ** 2 + H ** 2)

    # Map samples to height profile indices
    profile_len = len(height_profile)
    idx_float = x_samples / geom.range_m * (profile_len - 1)
    idx = np.clip(idx_float.astype(int), 0, profile_len - 1)

    heights = height_profile[idx]
    mats = material_profile[idx]

    # Incidence angle
    flat_z = H - heights  # depth below sonar after seabed height
    flat_z = np.maximum(flat_z, 0.1)
    theta_inc = np.arctan2(x_samples, flat_z)

    # Transmission loss
    TL = _transmission_loss(r_samples, alpha)

    # Backscatter strength per material
    BS = np.zeros(n_samples, dtype=np.float32)
    for mat_idx, mat in enumerate(Material):
        props = get_props(mat)
        mask = mats == mat_idx
        if mask.any():
            BS[mask] = _lambert_bs(theta_inc[mask], props.mu_db)

    # Echo level
    I_db = geom.source_level_db - 2.0 * TL + BS

    # Acoustic shadow detection (simplified occlusion)
    occlusion = _compute_occlusion(height_profile, x_samples, H)

    # Apply shadow: set to noise floor
    I_db = np.where(occlusion, noise_floor_db, I_db)

    # Add multiplicative K-speckle
    # Use per-material nu
    nu_map = np.array([
        get_props(mat).k_nu for mat in Material
    ], dtype=np.float32)
    nu = nu_map[np.clip(mats, 0, len(nu_map) - 1)]
    mean_nu = float(nu.mean())
    speckle = _k_speckle(mean_nu, n_samples, rng)
    I_linear = 10.0 ** (I_db / 10.0) * speckle
    I_linear = np.maximum(I_linear, 0.0)

    # TVG (time-varied gain) compensation — removes TL for display
    if add_tvg:
        tvg = 10.0 ** (2.0 * TL / 10.0)
        I_display = I_linear * tvg
    else:
        I_display = I_linear

    # Nadir gap: samples within water column (before first seabed return) → near 0
    nadir_samples = int(H / geom.range_m * n_samples)
    I_display[:nadir_samples] = 0.0

    # Surface multipath: echo at ~2*depth range
    depth = geom.altitude_m + 0.0  # simplified
    multipath_sample = int(2.0 * depth / geom.range_m * n_samples)
    if multipath_sample < n_samples:
        strength = 0.05 * np.max(I_display)
        I_display[max(0, multipath_sample - 2):min(n_samples, multipath_sample + 3)] += strength

    # Additive noise floor
    noise_floor_linear = 10.0 ** (noise_floor_db / 10.0)
    I_display += rng.exponential(noise_floor_linear * 0.1, n_samples)

    # Quantise to uint16
    max_val = np.max(I_display) + 1e-9
    I_uint16 = np.clip(I_display / max_val * 65535, 0, 65535).astype(np.uint16)

    return I_uint16


def _compute_occlusion(
    height_profile: np.ndarray,
    x_samples: np.ndarray,
    altitude_m: float,
) -> np.ndarray:
    """
    Compute which samples are in acoustic shadow.
    A sample is occluded if a higher object exists between it and the nadir.
    Returns bool array [N_samples].
    """
    n = len(x_samples)
    occluded = np.zeros(n, dtype=bool)

    profile_len = len(height_profile)
    idx = np.clip((x_samples / (x_samples[-1] + 1e-9) * (profile_len - 1)).astype(int), 0, profile_len - 1)
    heights_at_samples = height_profile[idx]

    max_elev_angle = -np.inf  # track maximum depression angle seen so far
    for i in range(n):
        x = x_samples[i]
        h = heights_at_samples[i]
        if x < 1e-3:
            continue
        # Elevation angle from sonar to top of object
        elev = (altitude_m - h) / (x + 1e-9)
        if elev < max_elev_angle:
            occluded[i] = True
        else:
            max_elev_angle = elev

    return occluded


def compute_shadow_length_m(
    object_height_m: float,
    object_ground_range_m: float,
    altitude_m: float,
) -> float:
    """
    Compute theoretical shadow length on the ground.
    Shadow = h * xo / (H - h)  [from similar triangles]
    Returns shadow length in metres.
    """
    if altitude_m <= object_height_m:
        return 0.0
    return object_height_m * object_ground_range_m / (altitude_m - object_height_m)
