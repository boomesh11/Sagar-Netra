"""
SagarNetra Detection — 2D OS-CFAR and Highlight-Shadow Pairing (Stage A).
Detects acoustic highlights and corresponding shadows cast away from the nadir.
Pairs highlights with shadows within 0.2m - 15.0m in the far-range direction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np
from scipy.ndimage import label, find_objects


@dataclass
class CFARCandidate:
    candidate_id: str
    side: str                          # "port" or "stbd"
    row_start: int                     # Along-track start pixel
    row_end: int                       # Along-track end pixel
    col_start: int                     # Range start pixel
    col_end: int                       # Range end pixel
    highlight_centroid_row: float      # Centroid of bright echo
    highlight_centroid_col: float
    shadow_centroid_row: float         # Centroid of acoustic shadow
    shadow_centroid_col: float
    shadow_length_m: float             # Measured length of shadow in meters
    ground_range_m: float              # Distance of target from nadir (m)
    snr_db: float                      # Signal to background ratio (dB)
    has_shadow: bool                   # Whether valid paired shadow was found
    highlight_area_px: int             # Pixel count of highlight
    shadow_area_px: int                # Pixel count of shadow


def os_cfar_2d(
    image: np.ndarray,
    guard_cells: int = 3,
    train_cells: int = 16,
    k_percentile: float = 75.0,
    pfa: float = 1e-3,
    min_highlight_ratio: float = 1.8,
    shadow_ratio: float = 0.35,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    2D Order-Statistic Constant False Alarm Rate (OS-CFAR) detector.
    
    Args:
        image: 2D float32 array [H, W] (typically normalised intensity [0, 1])
        guard_cells: half-width of guard window around test cell (G = 3)
        train_cells: half-width of outer training window (T = 16)
        k_percentile: rank percentile used for background estimate (default 75th percentile)
        pfa: nominal false alarm rate
        min_highlight_ratio: multiplier on background level for highlight detection
        shadow_ratio: fraction of background level below which pixels are classified as shadow
        
    Returns:
        highlight_mask: boolean mask of detected highlights
        shadow_mask: boolean mask of detected acoustic shadows
        background_est: estimated local background level array
    """
    h, w = image.shape
    highlight_mask = np.zeros((h, w), dtype=bool)
    shadow_mask = np.zeros((h, w), dtype=bool)

    # For fast execution, estimate local background using uniform / box filters with inner subtraction
    from scipy.ndimage import uniform_filter

    outer_size = 2 * train_cells + 1
    inner_size = 2 * guard_cells + 1

    # Outer training window average
    outer_sum = uniform_filter(image.astype(np.float32), size=outer_size, mode="reflect") * (outer_size * outer_size)
    inner_sum = uniform_filter(image.astype(np.float32), size=inner_size, mode="reflect") * (inner_size * inner_size)

    n_train_total = (outer_size * outer_size) - (inner_size * inner_size)
    n_train_total = max(n_train_total, 1)

    train_mean = (outer_sum - inner_sum) / n_train_total
    background_est = np.maximum(train_mean, 1e-4)

    # Calculate local variance in training window
    outer_sq = uniform_filter(image.astype(np.float32)**2, size=outer_size, mode="reflect") * (outer_size * outer_size)
    inner_sq = uniform_filter(image.astype(np.float32)**2, size=inner_size, mode="reflect") * (inner_size * inner_size)
    train_var = np.maximum((outer_sq - inner_sq) / n_train_total - background_est**2, 1e-5)
    train_std = np.sqrt(train_var)

    # For normalized imagery [0, 1] (or dynamic range compressed):
    if np.max(image) <= 1.05:
        k_factor = max(1.5, float(-np.log10(pfa) * 0.70))
        thresh = np.minimum(background_est + k_factor * train_std, 0.98)
        highlight_mask = image > thresh
        shadow_thresh = np.maximum(background_est - 1.2 * train_std, background_est * shadow_ratio)
        shadow_mask = (image < shadow_thresh) & (background_est > 0.08)
    else:
        alpha = max(min_highlight_ratio, float(-np.log(pfa) * 0.35))
        highlight_mask = image > (alpha * background_est)
        shadow_mask = (image < (shadow_ratio * background_est)) & (background_est > 0.05)

    return highlight_mask, shadow_mask, background_est


def pair_highlights_and_shadows(
    highlight_mask: np.ndarray,
    shadow_mask: np.ndarray,
    image: np.ndarray,
    background_est: np.ndarray,
    ground_res_m: float = 0.10,
    side: str = "port",
    min_shadow_dist_m: float = 0.2,
    max_shadow_dist_m: float = 15.0,
    min_highlight_area_px: int = 4,
    min_shadow_area_px: int = 6,
) -> List[CFARCandidate]:
    """
    Pairs each highlight connected component with its corresponding acoustic shadow.
    In side-scan sonar, the shadow MUST lie in the far-range direction (away from nadir).
    For a ground-range image, column index 0 is nadir, and column increases with ground range.
    Therefore, the shadow must appear at col_shadow >= col_highlight.
    
    Args:
        highlight_mask: [H, W] bool
        shadow_mask: [H, W] bool
        image: [H, W] float32
        background_est: [H, W] float32
        ground_res_m: pixel size in meters (0.10 m)
        side: "port" or "stbd"
        min_shadow_dist_m: min distance between highlight and shadow (0.2 m)
        max_shadow_dist_m: max search distance for shadow (15.0 m)
        
    Returns:
        List of CFARCandidate objects.
    """
    labeled_highlights, num_highlights = label(highlight_mask)
    if num_highlights == 0:
        return []

    labeled_shadows, num_shadows = label(shadow_mask)

    min_search_px = max(1, int(round(min_shadow_dist_m / ground_res_m)))
    max_search_px = int(round(max_shadow_dist_m / ground_res_m))

    candidates: List[CFARCandidate] = []
    hl_slices = find_objects(labeled_highlights)

    for i, s in enumerate(hl_slices, 1):
        if s is None:
            continue
        row_slice, col_slice = s
        hl_pixels = (labeled_highlights[s] == i)
        area = int(np.sum(hl_pixels))
        if area < min_highlight_area_px:
            continue

        # Highlight centroid
        y_indices, x_indices = np.where(hl_pixels)
        c_row = float(row_slice.start + np.mean(y_indices))
        c_col = float(col_slice.start + np.mean(x_indices))

        # Look in the far-range direction (col > col_slice.stop)
        # Search window along-track: within +/- 8 pixels (0.8 m) of highlight centroid
        r_min = max(0, int(c_row - 8))
        r_max = min(image.shape[0], int(c_row + 9))
        c_search_start = min(image.shape[1], col_slice.stop)
        c_search_end = min(image.shape[1], col_slice.stop + max_search_px)

        has_shadow = False
        shadow_len_m = 0.0
        sh_c_row = c_row
        sh_c_col = c_col
        sh_area = 0

        if c_search_end > c_search_start:
            search_region = shadow_mask[r_min:r_max, c_search_start:c_search_end]
            if np.any(search_region):
                # Found shadow pixels!
                sy, sx = np.where(search_region)
                sh_area = len(sx)
                if sh_area >= min_shadow_area_px:
                    has_shadow = True
                    # Shadow start and end along range
                    sh_col_start_local = int(np.min(sx))
                    sh_col_end_local = int(np.max(sx))
                    shadow_len_m = (sh_col_end_local - sh_col_start_local + 1) * ground_res_m

                    sh_c_row = float(r_min + np.mean(sy))
                    sh_c_col = float(c_search_start + np.mean(sx))

        # Calculate bounding box encompassing highlight and shadow
        bb_r_start = max(0, int(min(row_slice.start, sh_c_row - 4)))
        bb_r_end = min(image.shape[0], int(max(row_slice.stop, sh_c_row + 5)))
        bb_c_start = max(0, int(col_slice.start - 2))
        bb_c_end = min(image.shape[1], int(max(col_slice.stop + int(shadow_len_m / ground_res_m) + 4, col_slice.stop + 4)))

        # SNR calculation
        hl_intensity = float(np.mean(image[s][hl_pixels]))
        bg_level = float(np.mean(background_est[s][hl_pixels]))
        snr_ratio = max(hl_intensity / max(bg_level, 1e-4), 1.0)
        snr_db = 10.0 * float(np.log10(snr_ratio))

        ground_range_m = c_col * ground_res_m

        cand = CFARCandidate(
            candidate_id=f"cfar_{side}_{int(c_row)}_{int(c_col)}",
            side=side,
            row_start=bb_r_start,
            row_end=bb_r_end,
            col_start=bb_c_start,
            col_end=bb_c_end,
            highlight_centroid_row=c_row,
            highlight_centroid_col=c_col,
            shadow_centroid_row=sh_c_row,
            shadow_centroid_col=sh_c_col,
            shadow_length_m=shadow_len_m,
            ground_range_m=ground_range_m,
            snr_db=snr_db,
            has_shadow=has_shadow,
            highlight_area_px=area,
            shadow_area_px=sh_area,
        )
        candidates.append(cand)

    return candidates
