"""
SagarNetra Geotagging — Physical Target Dimensions & Oriented Bounding Box.
Estimates real-world length, width, orientation, area, and aspect ratio
from ground-range binary masks using Principal Component Analysis (PCA).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np


@dataclass
class PhysicalDimensions:
    length_m: float           # Longest principal dimension (metres)
    width_m: float            # Orthogonal width dimension (metres)
    height_m: Optional[float] # Height from acoustic shadow geometry (metres)
    orientation_deg: float    # Major axis orientation clockwise from North (0 - 180 deg)
    area_m2: float            # Physical surface footprint area (m^2)
    aspect_ratio: float       # length / max(width, 0.1)


def compute_physical_dimensions(
    mask: np.ndarray,
    res_across_m: float = 0.10,
    res_along_m: float = 0.10,
    towfish_heading_deg: float = 0.0,
    height_m: Optional[float] = None,
) -> PhysicalDimensions:
    """
    Computes oriented physical dimensions from a 2D binary segmentation mask.
    
    Args:
        mask: 2D boolean or binary numpy array [H, W] (along-track rows, across-track cols)
        res_across_m: Metres per pixel across-track
        res_along_m: Metres per pixel along-track
        towfish_heading_deg: Heading of towfish clockwise from North
        height_m: Target height derived from shadow length
    """
    pts = np.argwhere(mask > 0)  # Shape [N, 2]: (row_idx, col_idx)
    if len(pts) < 3:
        # Fallback for point-like detections
        pixel_count = max(len(pts), 1)
        area_m2 = pixel_count * res_across_m * res_along_m
        dim_m = math.sqrt(area_m2)
        return PhysicalDimensions(
            length_m=round(dim_m, 2),
            width_m=round(dim_m, 2),
            height_m=round(height_m, 2) if height_m is not None else None,
            orientation_deg=round(towfish_heading_deg, 1),
            area_m2=round(area_m2, 2),
            aspect_ratio=1.0,
        )

    # Convert coordinates to metric space: Y = row * res_along, X = col * res_across
    # (Along-track = Y, Across-track = X)
    y_m = pts[:, 0] * res_along_m
    x_m = pts[:, 1] * res_across_m

    pts_metric = np.column_stack([x_m, y_m])
    mean_center = np.mean(pts_metric, axis=0)
    centered = pts_metric - mean_center

    # Covariance matrix and PCA
    cov = np.cov(centered, rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)

    # Order by largest eigenvalue
    sort_idx = np.argsort(eigvals)[::-1]
    eigvals = eigvals[sort_idx]
    eigvecs = eigvecs[:, sort_idx]

    # Project points onto principal axes
    proj_major = centered @ eigvecs[:, 0]
    proj_minor = centered @ eigvecs[:, 1]

    # Robust length & width: 95th percentile span to reject outlier pixels
    length_m = float(np.percentile(proj_major, 97.5) - np.percentile(proj_major, 2.5))
    width_m = float(np.percentile(proj_minor, 97.5) - np.percentile(proj_minor, 2.5))

    # Minimum bounding constraint
    length_m = max(length_m, res_along_m)
    width_m = max(width_m, res_across_m)

    if width_m > length_m:
        length_m, width_m = width_m, length_m

    # Major axis orientation relative to along-track axis (Y)
    v_major = eigvecs[:, 0]
    angle_local_deg = math.degrees(math.atan2(v_major[0], v_major[1]))

    # Absolute orientation relative to North
    abs_orient_deg = (towfish_heading_deg + angle_local_deg) % 180.0

    area_m2 = float(len(pts) * res_across_m * res_along_m)
    aspect_ratio = float(length_m / max(width_m, 0.05))

    return PhysicalDimensions(
        length_m=round(length_m, 2),
        width_m=round(width_m, 2),
        height_m=round(height_m, 2) if height_m is not None else None,
        orientation_deg=round(abs_orient_deg, 1),
        area_m2=round(area_m2, 2),
        aspect_ratio=round(aspect_ratio, 2),
    )
