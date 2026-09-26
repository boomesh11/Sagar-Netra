"""
SagarNetra Preprocessing — Acoustic Feature Stack Generator.
Constructs a physics-grounded 3-channel representation fed to detectors instead of RGB:
- Channel 0: Normalised despeckled acoustic intensity [0, 1]
- Channel 1: Acoustic shadow probability map [0, 1]
- Channel 2: Multi-scale ridge / line detector map (Sato filter, scales 1-3 px) [0, 1]
"""
from __future__ import annotations

import numpy as np


def compute_shadow_probability_map(
    intensity: np.ndarray,
    local_window: int = 31,
    shadow_factor: float = 0.35,
) -> np.ndarray:
    """
    Computes an acoustic shadow probability map [0, 1].
    Shadows in side-scan sonar are regions where backscatter is near the acoustic noise floor,
    substantially lower than the surrounding seabed ambient level.
    """
    h, w = intensity.shape
    # Estimate local background level using box filter
    from backend.sagarnetra.preprocess.despeckle import _box_filter_2d
    local_mean = _box_filter_2d(intensity, local_window)
    local_mean = np.maximum(local_mean, 0.05)

    # Ratio of intensity to local background
    ratio = intensity / local_mean

    # Shadow probability: high when ratio is below shadow_factor
    # Sigmoidal transition around shadow_factor
    steepness = 12.0
    shadow_prob = 1.0 / (1.0 + np.exp(steepness * (ratio - shadow_factor)))
    return np.clip(shadow_prob, 0.0, 1.0).astype(np.float32)


try:
    from scipy.ndimage import gaussian_filter

    def _gaussian_blur_2d(img: np.ndarray, sigma: float) -> np.ndarray:
        return gaussian_filter(img.astype(np.float32), sigma=sigma, mode="reflect")

except ImportError:
    def _gaussian_blur_2d(img: np.ndarray, sigma: float) -> np.ndarray:
        radius = int(np.ceil(3.0 * sigma))
        x = np.arange(-radius, radius + 1)
        k = np.exp(-0.5 * (x / sigma)**2)
        k = k / np.sum(k)
        # Separable convolution along rows then cols
        res = np.zeros_like(img, dtype=np.float32)
        for r in range(img.shape[0]):
            res[r] = np.convolve(img[r], k, mode="same")
        for c in range(img.shape[1]):
            res[:, c] = np.convolve(res[:, c], k, mode="same")
        return res


def sato_ridge_filter(
    intensity: np.ndarray,
    scales: tuple[float, ...] = (1.0, 2.0, 3.0),
) -> np.ndarray:
    """
    Sato multi-scale ridge/tubular filter for highlighting linear structures:
    ropes, cables, pipes, and net headrope/footrope lines.
    
    Computes Hessian eigenvalues across scales and takes the maximum line response.
    """
    max_response = np.zeros_like(intensity, dtype=np.float32)

    for sigma in scales:
        smoothed = _gaussian_blur_2d(intensity, sigma)
        
        # Second derivatives using central finite differences
        # Ixx
        dxx = np.zeros_like(smoothed)
        dxx[:, 1:-1] = smoothed[:, 2:] - 2.0 * smoothed[:, 1:-1] + smoothed[:, :-2]
        
        # Iyy
        dyy = np.zeros_like(smoothed)
        dyy[1:-1, :] = smoothed[2:, :] - 2.0 * smoothed[1:-1, :] + smoothed[:-2, :]
        
        # Ixy
        dxy = np.zeros_like(smoothed)
        dxy[1:-1, 1:-1] = (
            smoothed[2:, 2:] - smoothed[2:, :-2] - smoothed[:-2, 2:] + smoothed[:-2, :-2]
        ) / 4.0

        # Eigenvalues of symmetric 2x2 matrix:
        # trace = dxx + dyy, det = dxx * dyy - dxy^2
        # lambda1,2 = (trace +- sqrt(trace^2 - 4*det)) / 2
        trace = dxx + dyy
        det = dxx * dyy - (dxy**2)
        disc = np.maximum(trace**2 - 4.0 * det, 0.0)
        sqrt_disc = np.sqrt(disc)

        l1 = 0.5 * (trace + sqrt_disc)
        l2 = 0.5 * (trace - sqrt_disc)

        # For bright tubular/linear ridge on dark background, eigenvalue with larger magnitude is negative
        # Select eigenvalue with most negative sign
        min_l = np.minimum(l1, l2)
        response = np.maximum(-min_l, 0.0) * (sigma**2)  # Scale-normalised response
        max_response = np.maximum(max_response, response)

    # Normalise response to [0, 1]
    p99 = float(np.percentile(max_response, 99.5)) if np.max(max_response) > 0 else 1.0
    norm_ridge = np.clip(max_response / max(p99, 1e-4), 0.0, 1.0)
    return norm_ridge.astype(np.float32)


def generate_feature_stack(
    despeckled_intensity: np.ndarray,
    shadow_map: np.ndarray | None = None,
    line_map: np.ndarray | None = None,
) -> np.ndarray:
    """
    Combines the 3 channels into a single feature stack array [H, W, 3].
    
    Channels:
    - ch0: Despeckled intensity [0, 1]
    - ch1: Shadow probability [0, 1]
    - ch2: Sato ridge / line score [0, 1]
    """
    h, w = despeckled_intensity.shape
    ch0 = np.clip(despeckled_intensity, 0.0, 1.0).astype(np.float32)

    if shadow_map is None:
        ch1 = compute_shadow_probability_map(ch0)
    else:
        ch1 = np.clip(shadow_map, 0.0, 1.0).astype(np.float32)

    if line_map is None:
        ch2 = sato_ridge_filter(ch0)
    else:
        ch2 = np.clip(line_map, 0.0, 1.0).astype(np.float32)

    stack = np.stack([ch0, ch1, ch2], axis=-1)
    return stack
