"""
SagarNetra Preprocessing — Speckle Reduction (Enhanced Lee Filter).
7x7 adaptive despeckling filter that eliminates multiplicative acoustic speckle
in homogeneous seabed zones while preserving sharp highlight edges and dark acoustic shadows.
"""
from __future__ import annotations

from typing import Tuple
import numpy as np


try:
    from scipy.ndimage import uniform_filter

    def _box_filter_2d(img: np.ndarray, ksize: int = 7) -> np.ndarray:
        return uniform_filter(img.astype(np.float32), size=ksize, mode="reflect")

except ImportError:
    def _box_filter_2d(img: np.ndarray, ksize: int = 7) -> np.ndarray:
        pad = ksize // 2
        padded = np.pad(img.astype(np.float32), pad, mode="reflect")
        integral = np.pad(np.cumsum(np.cumsum(padded, axis=0), axis=1), ((1, 0), (1, 0)), mode="constant")
        h, w = img.shape
        y1, y2 = np.arange(h), np.arange(h) + ksize
        x1, x2 = np.arange(w), np.arange(w) + ksize
        Y2, X2 = np.ix_(y2, x2)
        Y1, X1 = np.ix_(y1, x1)
        s = integral[Y2, X2] - integral[Y1, X2] - integral[Y2, X1] + integral[Y1, X1]
        return (s / (ksize * ksize)).astype(np.float32)


def enhanced_lee_filter(
    image: np.ndarray,
    window_size: int = 7,
    cu: float = 0.28,
    cmax: float = 0.60,
    k_damp: float = 1.0,
) -> np.ndarray:
    """
    Enhanced Lee filter for side-scan sonar despeckling.
    
    Args:
        image: 2D float32 image array [H, W], values typically in [0, 1]
        window_size: size of local neighbourhood (odd integer, default 7)
        cu: noise variation coefficient (typically ~0.25 - 0.35)
        cmax: upper threshold beyond which structure is preserved without smoothing
        k_damp: damping coefficient
        
    Returns:
        Despeckled float32 image preserving edges and shadows.
    """
    img = np.maximum(image.astype(np.float32), 1e-6)
    
    # Local mean and local mean of squares
    mean = _box_filter_2d(img, window_size)
    mean_sq = _box_filter_2d(img**2, window_size)
    
    # Local variance: Var = E[X^2] - (E[X])^2
    variance = np.maximum(mean_sq - mean**2, 0.0)
    std = np.sqrt(variance)
    
    # Local coefficient of variation: Ci = std / mean
    ci = std / np.maximum(mean, 1e-5)
    
    # Compute weighting factor W
    # Case 1: Ci <= Cu -> homogeneous region -> W = 1.0 (pure mean smoothing)
    # Case 2: Ci >= Cmax -> high-contrast point/edge -> W = 0.0 (preserve original)
    # Case 3: Cu < Ci < Cmax -> transitional texture -> exponential weighting
    w = np.zeros_like(img)
    
    homo_mask = ci <= cu
    edge_mask = ci >= cmax
    trans_mask = (~homo_mask) & (~edge_mask)
    
    w[homo_mask] = 1.0
    w[edge_mask] = 0.0
    
    if np.any(trans_mask):
        denom = np.maximum(cmax - ci[trans_mask], 1e-4)
        num = k_damp * (ci[trans_mask] - cu)
        w[trans_mask] = np.exp(-num / denom)
        
    # Output = mean * W + img * (1 - W)
    filtered = mean * w + img * (1.0 - w)
    return np.clip(filtered, 0.0, 1.0).astype(np.float32)


def despeckle_waterfall(
    waterfall: np.ndarray,
    window_size: int = 7,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Applies speckle filtering to waterfall, returning (despeckled, raw).
    """
    raw = waterfall.astype(np.float32)
    despeckled = enhanced_lee_filter(raw, window_size=window_size)
    return despeckled, raw
