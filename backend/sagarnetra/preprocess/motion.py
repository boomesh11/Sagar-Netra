"""
SagarNetra Preprocessing — Motion Compensation & Along-Track Resampling.
Resamples waterfall rows by distance travelled (speed over ground) to a uniform
spatial grid (default 0.10 m/row), compensating for vessel speed fluctuations,
heave, and yaw/crab angles.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import numpy as np


@dataclass
class MotionCorrectionResult:
    resampled_image: np.ndarray       # Shape: [num_along_bins, num_across_bins]
    along_track_dist_m: np.ndarray    # Shape: [num_along_bins], cumulative track distance in meters
    along_res_m: float                # Along-track resolution in meters (e.g. 0.10 m)
    original_ping_indices: np.ndarray # Shape: [num_along_bins], corresponding original ping indices (fractional)


def compute_cumulative_distance(
    timestamps_s: np.ndarray,
    speeds_mps: np.ndarray,
) -> np.ndarray:
    """
    Integrates vessel speed over time intervals to obtain cumulative along-track distance.
    """
    n = len(timestamps_s)
    if n == 0:
        return np.array([], dtype=np.float32)
    if n == 1:
        return np.array([0.0], dtype=np.float32)

    dt = np.diff(timestamps_s)
    # Ensure dt is strictly non-negative
    dt = np.maximum(dt, 0.0)

    # Average speed in each interval
    v_mid = 0.5 * (speeds_mps[:-1] + speeds_mps[1:])
    v_mid = np.maximum(v_mid, 0.05)  # clamp minimum speed to prevent division by zero

    step_dist = v_mid * dt
    cum_dist = np.zeros(n, dtype=np.float32)
    cum_dist[1:] = np.cumsum(step_dist)
    return cum_dist


def resample_along_track(
    ground_image: np.ndarray,
    timestamps_s: np.ndarray,
    speeds_mps: np.ndarray,
    along_res_m: float = 0.10,
) -> MotionCorrectionResult:
    """
    Resamples a ground-range waterfall along the track dimension to achieve uniform spatial pixels.
    
    Args:
        ground_image: [num_pings, num_across_bins]
        timestamps_s: [num_pings] timestamps
        speeds_mps: [num_pings] speed over ground in m/s
        along_res_m: along-track spatial step (meters per row)
        
    Returns:
        MotionCorrectionResult with spatially square-pixel waterfall.
    """
    n_pings, n_across = ground_image.shape
    if n_pings < 2:
        return MotionCorrectionResult(
            resampled_image=ground_image.copy(),
            along_track_dist_m=np.array([0.0], dtype=np.float32),
            along_res_m=along_res_m,
            original_ping_indices=np.array([0.0], dtype=np.float32),
        )

    cum_dist = compute_cumulative_distance(timestamps_s, speeds_mps)
    total_dist = float(cum_dist[-1])
    n_along_bins = max(int(np.ceil(total_dist / along_res_m)), 1)
    target_dists = np.arange(n_along_bins, dtype=np.float32) * along_res_m

    # Interpolate ping indices for each along-track target distance
    ping_indices_continuous = np.arange(n_pings, dtype=np.float32)
    resampled_indices = np.interp(target_dists, cum_dist, ping_indices_continuous)

    # Interpolate across each range column
    resampled_image = np.zeros((n_along_bins, n_across), dtype=np.float32)
    for col in range(n_across):
        resampled_image[:, col] = np.interp(
            target_dists,
            cum_dist,
            ground_image[:, col],
        )

    return MotionCorrectionResult(
        resampled_image=resampled_image,
        along_track_dist_m=target_dists,
        along_res_m=along_res_m,
        original_ping_indices=resampled_indices,
    )


def compensate_yaw(
    waterfall: np.ndarray,
    yaw_deg: np.ndarray,
    ground_res_m: float = 0.10,
    along_res_m: float = 0.10,
) -> np.ndarray:
    """
    Compensates for towfish yaw (crab angle) relative to track line.
    Applies along-track shear shift: delta_y = x * tan(yaw_rad).
    """
    n_rows, n_cols = waterfall.shape
    if len(yaw_deg) != n_rows:
        return waterfall

    out = np.zeros_like(waterfall)
    yaw_rad = np.deg2rad(yaw_deg)

    for c in range(n_cols):
        ground_x = c * ground_res_m
        # Shear shift in along-track bins
        shifts = (ground_x * np.tan(yaw_rad)) / along_res_m
        y_orig = np.arange(n_rows, dtype=np.float32)
        y_query = y_orig - shifts
        out[:, c] = np.interp(y_query, y_orig, waterfall[:, c], left=0.0, right=0.0)

    return out
