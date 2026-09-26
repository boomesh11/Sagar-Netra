"""
SagarNetra Preprocessing — Empirical Gain Normalisation (EGN) & Dynamic Range Compression.
Normalises acoustic backscatter decay across range bins using a sliding window mean profile,
then applies log compression and scales to [0, 1].
"""
from __future__ import annotations

import numpy as np


def empirical_gain_normalisation(
    waterfall: np.ndarray,
    window_pings: int = 200,
    min_gain_clip: float = 1e-3,
) -> np.ndarray:
    """
    Applies Empirical Gain Normalisation (EGN) to eliminate across-track intensity decay
    caused by beam patterns, spreading loss, and grazing angle variations.
    
    Args:
        waterfall: [num_pings, num_range_bins] float32 array
        window_pings: sliding along-track window size (default: 200 pings)
        min_gain_clip: minimum denominator threshold to avoid division by zero
        
    Returns:
        Gain-normalised waterfall of same shape, with flat average response across range.
    """
    n_pings, n_cols = waterfall.shape
    if n_pings == 0 or n_cols == 0:
        return waterfall.copy()

    out = np.zeros_like(waterfall, dtype=np.float32)

    if n_pings <= window_pings:
        # Full swath mean profile
        mean_profile = np.mean(waterfall, axis=0)
        global_mean = float(np.mean(mean_profile))
        gain_curve = np.maximum(mean_profile, min_gain_clip)
        scale_factor = global_mean / gain_curve
        out = waterfall * scale_factor[np.newaxis, :]
    else:
        # Sliding window EGN
        half_w = window_pings // 2
        for i in range(n_pings):
            i_start = max(0, i - half_w)
            i_end = min(n_pings, i + half_w + 1)
            win_profile = np.mean(waterfall[i_start:i_end], axis=0)
            win_mean = float(np.mean(win_profile))
            gain_curve = np.maximum(win_profile, min_gain_clip)
            scale = win_mean / gain_curve
            out[i] = waterfall[i] * scale

    return out


def log_compress_and_scale(
    waterfall: np.ndarray,
    dynamic_range_db: float = 40.0,
    eps: float = 1e-4,
) -> np.ndarray:
    """
    Logarithmic compression mapping high dynamic range sonar backscatter into [0.0, 1.0].
    
    I_db = 10 * log10(I + eps)
    Scaled relative to the upper percentile (e.g. 99.5%) down through dynamic_range_db.
    """
    pos_data = np.maximum(waterfall, 0.0)
    db = 10.0 * np.log10(pos_data + eps)

    # Reference peak at 99.5th percentile to resist high outlier spikes
    p99 = float(np.percentile(db, 99.5))
    min_db = p99 - dynamic_range_db

    scaled = (db - min_db) / dynamic_range_db
    return np.clip(scaled, 0.0, 1.0).astype(np.float32)
