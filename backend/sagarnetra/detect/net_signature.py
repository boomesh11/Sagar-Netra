"""
SagarNetra Detection — Net Signature Head.
Physically grounded feature extractor for ghost nets and fishing gear:
(a) LoG blob detection for floats and sinkers (0.08m - 0.50m)
(b) Chain finder: graph with edges 0.3m - 3.0m -> MST -> longest smooth paths;
    scores spacing regularity (CV < 0.35) and curvature smoothness
(c) Ridge skeleton length >= 2m (ropes, headrope/footrope lines)
(d) Mesh texture energy (Gabor filter bank tuned to 2-8 px periods)
Outputs S_net in [0, 1] + heatmap + human-readable evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np
from scipy.ndimage import gaussian_laplace, gaussian_filter, label


@dataclass
class NetSignatureResult:
    s_net: float                       # Net confidence score in [0.0, 1.0]
    float_chain_detected: bool         # True if periodic float chain was detected
    num_floats: int                    # Count of floats/sinkers in best chain
    mean_spacing_m: float              # Average spacing between consecutive floats (m)
    spacing_cv: float                  # Spacing coefficient of variation (std/mean)
    ridge_length_m: float              # Total continuous rope/skeleton length (m)
    mesh_energy: float                 # Gabor mesh texture energy [0.0, 1.0]
    evidence: str                      # Human-readable justification string
    heatmap: np.ndarray                # Net signature probability heatmap [H, W]


def detect_float_blobs(
    intensity: np.ndarray,
    ground_res_m: float = 0.10,
    min_radius_m: float = 0.08,
    max_radius_m: float = 0.50,
    threshold: float = 0.01,
) -> List[Tuple[float, float, float]]:
    """
    Detects small bright point-like blobs (floats and sinkers) using multi-scale
    Hessian determinant (DoH) / Laplacian of Gaussian.
    Discriminated point nodes even when connected by a headrope / footrope line.
    
    Returns:
        List of (row, col, radius_px) tuples.
    """
    from scipy.ndimage import gaussian_filter, maximum_filter
    h, w = intensity.shape
    min_sigma = max(min_radius_m / ground_res_m / np.sqrt(2), 0.7)
    max_sigma = max_radius_m / ground_res_m / np.sqrt(2)
    sigmas = np.linspace(min_sigma, max_sigma, num=3)

    best_resp = np.zeros((h, w), dtype=np.float32)
    best_scale = np.zeros((h, w), dtype=np.float32)

    for s in sigmas:
        smooth = gaussian_filter(intensity.astype(np.float32), s, mode="reflect")
        # Hessian 2nd derivatives
        dxx = np.zeros_like(smooth)
        dxx[:, 1:-1] = smooth[:, 2:] - 2.0 * smooth[:, 1:-1] + smooth[:, :-2]
        dyy = np.zeros_like(smooth)
        dyy[1:-1, :] = smooth[2:, :] - 2.0 * smooth[1:-1, :] + smooth[:-2, :]
        dxy = np.zeros_like(smooth)
        dxy[1:-1, 1:-1] = (
            smooth[2:, 2:] - smooth[2:, :-2] - smooth[:-2, 2:] + smooth[:-2, :-2]
        ) / 4.0

        # Determinant of Hessian (positive for point blobs, near 0 for lines)
        det = (dxx * dyy - dxy**2) * (s**4)
        # We only want bright blobs on darker background (trace < 0)
        trace = dxx + dyy
        blob_resp = np.where((det > 0) & (trace < 0), det, 0.0)

        update_mask = blob_resp > best_resp
        best_resp[update_mask] = blob_resp[update_mask]
        best_scale[update_mask] = s

    # Find 2D local maxima
    win_size = 5
    max_filt = maximum_filter(best_resp, size=win_size, mode="constant")
    is_peak = (best_resp == max_filt) & (best_resp > threshold) & (intensity > np.mean(intensity) + 0.05)

    y_idx, x_idx = np.where(is_peak)
    blobs: List[Tuple[float, float, float]] = []
    for r, c in zip(y_idx, x_idx):
        rad = float(best_scale[r, c] * np.sqrt(2))
        blobs.append((float(r), float(c), rad))

    return blobs


def _build_mst_chains(
    points: np.ndarray,
    ground_res_m: float = 0.10,
    min_dist_m: float = 0.3,
    max_dist_m: float = 3.0,
) -> Tuple[int, float, float]:
    """
    Finds chains of floats by building an adjacency graph of points separated by min_dist to max_dist,
    finding connected components / longest paths, and scoring spacing regularity (CV).
    
    Returns:
        (max_chain_length, mean_spacing_m, spacing_cv)
    """
    n = len(points)
    if n < 3:
        return 0, 0.0, 1.0

    # Compute pairwise Euclidean distance matrix
    dists = np.sqrt(np.sum((points[:, np.newaxis, :] - points[np.newaxis, :, :])**2, axis=-1)) * ground_res_m

    # Graph adjacency: connect points within realistic float spacing (0.3m to 3.0m)
    adj = (dists >= min_dist_m) & (dists <= max_dist_m)
    np.fill_diagonal(adj, False)

    # Simple greedy chain finder (path traversal)
    visited = set()
    best_chain: List[int] = []

    for start_node in range(n):
        if start_node in visited:
            continue
        # Greedy walk
        chain = [start_node]
        current = start_node
        chain_visited = {start_node}

        while True:
            neighbors = np.where(adj[current])[0]
            unvisited_neighbors = [nb for nb in neighbors if nb not in chain_visited]
            if not unvisited_neighbors:
                break
            # Pick closest neighbor
            next_node = min(unvisited_neighbors, key=lambda nb: dists[current, nb])
            chain.append(next_node)
            chain_visited.add(next_node)
            current = next_node

        if len(chain) > len(best_chain):
            best_chain = chain
            visited.update(chain)

    if len(best_chain) < 3:
        return len(best_chain), 0.0, 1.0

    # Calculate step distances along best chain
    step_dists = [dists[best_chain[i], best_chain[i + 1]] for i in range(len(best_chain) - 1)]
    mean_spacing = float(np.mean(step_dists))
    std_spacing = float(np.std(step_dists))
    cv = float(std_spacing / max(mean_spacing, 1e-4))

    return len(best_chain), mean_spacing, cv


def gabor_mesh_energy(
    intensity: np.ndarray,
    wavelengths: tuple[float, ...] = (3.0, 6.0),
    num_orientations: int = 2,
) -> Tuple[float, np.ndarray]:
    """
    Computes Gabor texture energy tuned to side-scan net mesh periods.
    Evaluates 4 representative Gabor kernels for fast CPU performance.
    
    Returns:
        (global_mesh_score in [0, 1], local_mesh_energy_map [H, W])
    """
    h, w = intensity.shape
    total_energy = np.zeros((h, w), dtype=np.float32)

    angles = np.linspace(0, np.pi, num_orientations, endpoint=False)

    for lam in wavelengths:
        sigma = 0.56 * lam
        radius = int(np.ceil(2.5 * sigma))
        y, x = np.mgrid[-radius:radius + 1, -radius:radius + 1]

        for theta in angles:
            x_theta = x * np.cos(theta) + y * np.sin(theta)
            y_theta = -x * np.sin(theta) + y * np.cos(theta)

            # Complex Gabor filter (real and imaginary parts for energy)
            envelope = np.exp(-0.5 * (x_theta**2 + y_theta**2) / (sigma**2))
            kernel_real = envelope * np.cos(2.0 * np.pi * x_theta / lam)
            kernel_imag = envelope * np.sin(2.0 * np.pi * x_theta / lam)

            # Normalise kernels
            kernel_real -= np.mean(kernel_real)
            kernel_real /= max(np.sum(np.abs(kernel_real)), 1e-5)
            kernel_imag -= np.mean(kernel_imag)
            kernel_imag /= max(np.sum(np.abs(kernel_imag)), 1e-5)

            # 2D correlation via scipy.ndimage
            from scipy.ndimage import convolve
            resp_r = convolve(intensity.astype(np.float32), kernel_real, mode="reflect")
            resp_i = convolve(intensity.astype(np.float32), kernel_imag, mode="reflect")
            mag = np.sqrt(resp_r**2 + resp_i**2)
            total_energy += mag

    # Normalise energy
    n_filters = len(wavelengths) * num_orientations
    avg_energy = total_energy / max(n_filters, 1)

    p99 = float(np.percentile(avg_energy, 99.0)) if np.max(avg_energy) > 0 else 1.0
    norm_energy = np.clip(avg_energy / max(p99, 1e-4), 0.0, 1.0)
    coverage = float(np.mean(norm_energy > 0.35))
    intensity_term = float(np.mean(norm_energy[norm_energy > 0.35])) if coverage > 0 else 0.0
    mesh_score = float(min(coverage * 4.0, 1.0) * intensity_term)

    return min(mesh_score, 1.0), norm_energy.astype(np.float32)


def evaluate_net_signature(
    intensity: np.ndarray,
    ridge_map: Optional[np.ndarray] = None,
    ground_res_m: float = 0.10,
) -> NetSignatureResult:
    """
    Evaluates complete Net Signature on a sonar image tile or candidate crop.
    
    Combines:
    1. Float/sinker LoG detection and chain regularity (CV < 0.35)
    2. Headrope / footrope skeleton length >= 2m
    3. Gabor mesh texture energy
    
    Produces S_net in [0, 1] and human-readable evidence.
    """
    h, w = intensity.shape

    # 1. Float blob detection
    blobs = detect_float_blobs(intensity, ground_res_m=ground_res_m)
    points = np.array([[b[0], b[1]] for b in blobs], dtype=np.float32) if blobs else np.empty((0, 2), dtype=np.float32)

    chain_len, mean_sp, sp_cv = _build_mst_chains(points, ground_res_m=ground_res_m)
    float_chain_detected = (chain_len >= 4 and sp_cv < 0.35)

    # 2. Rope / Skeleton ridge analysis
    if ridge_map is None:
        from backend.sagarnetra.preprocess.features import sato_ridge_filter
        ridge = sato_ridge_filter(intensity)
    else:
        ridge = ridge_map

    ridge_mask = ridge > 0.35
    labeled_ridge, num_ridge = label(ridge_mask)
    max_ridge_px = 0
    if num_ridge > 0:
        counts = np.bincount(labeled_ridge.ravel())[1:]
        max_ridge_px = int(np.max(counts)) if len(counts) > 0 else 0

    ridge_length_m = max_ridge_px * ground_res_m

    # 3. Gabor mesh texture energy
    mesh_score, mesh_heatmap = gabor_mesh_energy(intensity)

    # 4. Score fusion for S_net
    # Base weights:
    # - Float chain detected with good CV: major indicator (+0.45)
    # - Long continuous ridge line: (+0.30)
    # - Mesh texture energy: (+0.25)
    w_chain = 0.45 if float_chain_detected else (0.25 if chain_len >= 3 else 0.0)
    if chain_len >= 4 and sp_cv >= 0.35:
        # Partial credit for irregular chain
        w_chain = 0.20

    w_ridge = min(ridge_length_m / 4.0, 1.0) * 0.35
    w_mesh = mesh_score * 0.20

    s_net_raw = w_chain + w_ridge + w_mesh
    s_net = float(np.clip(s_net_raw, 0.0, 1.0))

    # Evidence string generation
    evidence_parts = []
    if chain_len >= 3:
        cv_note = "regular spacing" if sp_cv < 0.35 else "irregular spacing"
        evidence_parts.append(
            f"float chain of {chain_len} nodes (mean {mean_sp:.1f}m, CV={sp_cv:.2f}, {cv_note})"
        )
    if ridge_length_m >= 1.0:
        evidence_parts.append(f"headrope skeleton {ridge_length_m:.1f}m")
    if mesh_score > 0.25:
        evidence_parts.append(f"mesh texture energy {mesh_score:.2f}")

    if not evidence_parts:
        evidence = "No distinct net features (no float chain, short ridge, low mesh energy)"
    else:
        evidence = "; ".join(evidence_parts)

    # Combined heatmap
    heatmap = np.clip(0.4 * mesh_heatmap + 0.6 * ridge, 0.0, 1.0).astype(np.float32)

    return NetSignatureResult(
        s_net=s_net,
        float_chain_detected=float_chain_detected,
        num_floats=chain_len,
        mean_spacing_m=mean_sp,
        spacing_cv=sp_cv,
        ridge_length_m=ridge_length_m,
        mesh_energy=mesh_score,
        evidence=evidence,
        heatmap=heatmap,
    )
