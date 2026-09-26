"""
SagarNetra Preprocessing — Slant-Range Correction.
Converts slant-range sonar time series to uniform horizontal ground-range imagery.
x = sqrt(r^2 - H^2), removing the water column and normalizing pixel resolution.
Provides forward (slant -> ground) and inverse (ground -> slant) mappings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import numpy as np


@dataclass
class SlantRangeCorrectionResult:
    ground_image: np.ndarray       # Shape: [num_pings, num_ground_bins]
    ground_ranges_m: np.ndarray    # Shape: [num_ground_bins], horizontal distance from nadir in meters
    ground_res_m: float            # Ground pixel resolution in meters (e.g. 0.10 m)
    max_ground_range_m: float      # Maximum ground range covered


def slant_to_ground_indices(
    slant_ranges_m: np.ndarray,
    altitude_m: float,
    ground_res_m: float = 0.10,
    max_ground_range_m: float = 50.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes slant-range indices corresponding to uniform ground-range query points.
    
    Given ground range x_i:
        r_i = sqrt(x_i^2 + H^2)
    This calculates the exact slant sample index (fractional) for each ground bin.
    """
    n_ground_bins = int(np.ceil(max_ground_range_m / ground_res_m))
    ground_ranges = np.arange(n_ground_bins, dtype=np.float32) * ground_res_m

    # r = sqrt(x^2 + H^2)
    req_slant_ranges = np.sqrt(ground_ranges**2 + (altitude_m**2))

    # Convert required slant range to fractional slant bin index
    slant_res = slant_ranges_m[1] - slant_ranges_m[0] if len(slant_ranges_m) > 1 else 0.05
    slant_indices = req_slant_ranges / slant_res

    return ground_ranges, slant_indices


def correct_slant_range_ping(
    ping_samples: np.ndarray,
    altitude_m: float,
    sample_spacing_m: float,
    ground_res_m: float = 0.10,
    max_ground_range_m: float = 50.0,
    fill_value: float = 0.0,
) -> np.ndarray:
    """
    Performs slant-range correction for a single ping array (port or stbd).
    Resamples from non-linear ground spacing to a uniform ground grid via linear interpolation.
    """
    n_samples = len(ping_samples)
    slant_ranges = np.arange(n_samples, dtype=np.float32) * sample_spacing_m
    max_slant = slant_ranges[-1] if n_samples > 0 else 0.0

    n_ground_bins = int(np.ceil(max_ground_range_m / ground_res_m))
    ground_ranges = np.arange(n_ground_bins, dtype=np.float32) * ground_res_m

    req_slant = np.sqrt(ground_ranges**2 + (altitude_m**2))
    
    # Valid mask where required slant range is within available samples
    valid_mask = req_slant <= max_slant

    # Linear interpolation
    corrected = np.interp(
        req_slant,
        slant_ranges,
        ping_samples.astype(np.float32),
        left=fill_value,
        right=fill_value,
    )
    corrected[~valid_mask] = fill_value
    return corrected


def correct_slant_range_waterfall(
    waterfall: np.ndarray,
    altitudes_m: np.ndarray,
    sample_spacing_m: float,
    ground_res_m: float = 0.10,
    max_ground_range_m: float = 50.0,
) -> SlantRangeCorrectionResult:
    """
    Applies slant-range correction across all pings in a waterfall matrix.
    Vectorized over pings.
    
    Args:
        waterfall: [num_pings, num_slant_samples]
        altitudes_m: [num_pings] towfish altitude per ping
        sample_spacing_m: dr = c*dt/2 in meters
        ground_res_m: target ground grid resolution in meters
        max_ground_range_m: maximum ground range in meters
        
    Returns:
        SlantRangeCorrectionResult with uniform ground image [num_pings, num_ground_bins]
    """
    n_pings, n_samples = waterfall.shape
    n_ground_bins = int(np.ceil(max_ground_range_m / ground_res_m))
    ground_ranges = np.arange(n_ground_bins, dtype=np.float32) * ground_res_m
    slant_ranges = np.arange(n_samples, dtype=np.float32) * sample_spacing_m

    ground_image = np.zeros((n_pings, n_ground_bins), dtype=np.float32)

    for i in range(n_pings):
        alt = max(float(altitudes_m[i]), 0.1)
        ground_image[i] = correct_slant_range_ping(
            ping_samples=waterfall[i],
            altitude_m=alt,
            sample_spacing_m=sample_spacing_m,
            ground_res_m=ground_res_m,
            max_ground_range_m=max_ground_range_m,
        )

    return SlantRangeCorrectionResult(
        ground_image=ground_image,
        ground_ranges_m=ground_ranges,
        ground_res_m=ground_res_m,
        max_ground_range_m=max_ground_range_m,
    )


def ground_to_slant_coord(ground_x_m: float, altitude_m: float) -> float:
    """Computes exact slant range r = sqrt(x^2 + H^2)."""
    return float(np.sqrt(ground_x_m**2 + altitude_m**2))


def slant_to_ground_coord(slant_r_m: float, altitude_m: float) -> float:
    """Computes horizontal ground range x = sqrt(max(r^2 - H^2, 0))."""
    if slant_r_m < altitude_m:
        return 0.0
    return float(np.sqrt(slant_r_m**2 - altitude_m**2))
