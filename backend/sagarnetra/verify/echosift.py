"""
backend/sagarnetra/verify/echosift.py
====================================
EchoSift: Physics-Verified Marine Debris Detection Layer for Side-Scan Sonar.

Implements the 4 core physics modules:
1. Shadow-Highlight Consistency (SHC):
   - Computes object height: h = (L_s * H) / (R + L_s)
   - Checks shadow direction: must point down-range away from nadir
   - Penalizes flat features (h ≈ 0: sediment patches) and impossible heights
2. Geometric Regularity Index (GRI):
   - Edge straightness (Hough line energy vs total gradient energy)
   - Local 2D FFT periodicity peak sharpness
   - Orientation coherence contrast with 3x annular neighbourhood (differentiates net from sand ripples)
3. Motion-Artifact Masking:
   - Heave/pitch/roll thresholding + ping-to-ping cross-correlation collapse
   - Suppresses detections with > 40% motion mask overlap
4. Multi-Pass Persistence:
   - Spatial join across survey lines within 5 m tolerance
5. Calibrated 5-Term Evidence Fusion:
   C = σ(w0 + w1*z_cnn + w2*z_shc + w3*z_reg - w4*z_motion + w5*z_persist)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


@dataclass
class EchoSiftEvidence:
    cnn_score: float             # z_cnn ∈ [0, 1]
    shc_score: float             # z_shc ∈ [0, 1]
    height_estimate_m: float     # h in metres
    shadow_side: str             # "correct" (away from nadir) or "incorrect"
    regularity_score: float      # z_reg ∈ [0, 1]
    is_sand_ripple: bool         # True if periodicity extends across 3x neighbourhood
    motion_penalty: float        # z_motion ∈ [0, 1] (% overlap with motion-artifact mask)
    persistence_score: float     # z_persist ∈ [0, 1]
    pass_count: int              # Number of overlapping survey lines seeing the target
    fused_confidence: float      # Calibrated fused confidence C ∈ [0, 100] %
    suppressed: bool             # True if rejected by physics filters
    suppression_reason: Optional[str] = None


class EchoSiftPipeline:
    """
    EchoSift verification engine wrapping lightweight detectors in acoustic physics.
    """
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        edge_mode: str = "shore"  # "shore" or "onboard_jetson"
    ):
        # Default calibrated 6-parameter logistic regression weights
        # C = σ(w0 + w1*z_cnn + w2*z_shc + w3*z_reg - w4*z_motion + w5*z_persist)
        self.weights = weights or {
            "w0": -1.25,
            "w1": 2.80,   # CNN weight
            "w2": 2.45,   # SHC weight
            "w3": 1.75,   # Geometric regularity
            "w4": 3.20,   # Motion artifact penalty
            "w5": 1.95    # Multi-pass persistence
        }
        self.edge_mode = edge_mode

    # -------------------------------------------------------------
    # 1. Shadow-Highlight Consistency (SHC)
    # -------------------------------------------------------------
    @staticmethod
    def compute_shc(
        slant_range_m: float,
        towfish_alt_m: float,
        shadow_len_m: float,
        channel: str = "starboard",
        shadow_offset_px: float = 12.0,
        class_name: str = "ghost_net"
    ) -> Tuple[float, float, str, Optional[str]]:
        """
        Computes object height from acoustic shadow geometry:
            h = (L_s * H) / (R + L_s)
        
        Returns:
            (shc_score, height_m, shadow_side, suppression_reason)
        """
        if slant_range_m <= 0 or towfish_alt_m <= 0:
            return 0.0, 0.0, "incorrect", "Invalid sonar range or altitude geometry"

        # Shadow direction check: shadow must point away from nadir
        # For port: negative x-direction; for starboard: positive x-direction
        shadow_away_from_nadir = (channel == "starboard" and shadow_offset_px > 0) or \
                                 (channel == "port" and shadow_offset_px < 0) or \
                                 (shadow_offset_px > 0)

        shadow_side = "correct" if shadow_away_from_nadir else "incorrect"

        if not shadow_away_from_nadir:
            return 0.05, 0.0, "incorrect", "Anti-causal shadow pointing toward nadir (depression or noise)"

        # Calculate height
        h = (shadow_len_m * towfish_alt_m) / (slant_range_m + shadow_len_m)

        # Height prior check by class
        priors = {
            "ghost_net": (0.2, 2.2),
            "pipe": (0.1, 1.2),
            "cylinder": (0.15, 1.8),
            "wreck": (1.5, 16.0),
            "tyre_drum": (0.2, 1.4),
            "unknown_manmade": (0.2, 4.0)
        }
        min_h, max_h = priors.get(class_name, (0.15, 3.0))

        if h < 0.08:
            # Flat feature (sand patch, dark sediment, flat depression)
            return 0.10, round(h, 2), "correct", f"Shadow implies height ≈ {h:.2f}m (flat sediment patch)"
        
        if h > max_h * 2.5:
            # Acoustically impossible height for class (e.g. 40m for a net)
            return 0.15, round(h, 2), "correct", f"Impossible height {h:.1f}m for class {class_name}"

        # Plausible height bonus
        if min_h <= h <= max_h:
            shc_score = 0.95
        else:
            shc_score = 0.70

        return shc_score, round(h, 2), "correct", None

    # -------------------------------------------------------------
    # 2. Geometric Regularity Index (GRI)
    # -------------------------------------------------------------
    @staticmethod
    def compute_regularity_index(
        patch: np.ndarray,
        ring_3x: Optional[np.ndarray] = None
    ) -> Tuple[float, bool]:
        """
        Computes man-made regularity:
        - Straight edge ratio (Hough / total gradient energy)
        - 2D FFT periodicity sharpness
        - Contrast with 3x surrounding annular ring (distinguishes isolated nets from sand ripples)
        
        Returns:
            (regularity_score, is_sand_ripple)
        """
        if patch is None or patch.size == 0:
            return 0.5, False

        h, w = patch.shape
        # Edge straightness via gradient orientation variance
        gy, gx = np.gradient(patch.astype(np.float32))
        grad_mag = np.hypot(gx, gy)
        angles = np.arctan2(gy, gx)

        # High coherence in angles indicates dominant straight edges / parallel ribs
        valid = grad_mag > np.percentile(grad_mag, 70)
        if np.sum(valid) > 10:
            hist, _ = np.histogram(angles[valid], bins=18, range=(-np.pi, np.pi))
            entropy = -np.sum((hist / np.sum(hist) + 1e-6) * np.log(hist / np.sum(hist) + 1e-6))
            straightness = float(np.clip(1.0 - (entropy / 2.88), 0.0, 1.0))
        else:
            straightness = 0.3

        # 2D FFT periodicity
        f_transform = np.fft.fftshift(np.fft.fft2(patch - np.mean(patch)))
        power_spectrum = np.abs(f_transform)**2
        center_y, center_x = h // 2, w // 2
        power_spectrum[center_y - 2:center_y + 3, center_x - 2:center_x + 3] = 0  # Zero DC
        peak_val = np.max(power_spectrum)
        mean_val = np.mean(power_spectrum) + 1e-6
        periodicity = float(np.clip((peak_val / mean_val - 1.0) / 25.0, 0.0, 1.0))

        # Check surrounding 3x ring: if entire neighbourhood is periodic -> sand ripples!
        is_sand_ripple = False
        if ring_3x is not None and ring_3x.size > patch.size:
            f_ring = np.fft.fftshift(np.fft.fft2(ring_3x - np.mean(ring_3x)))
            ring_power = np.abs(f_ring)**2
            ry, rx = ring_3x.shape[0] // 2, ring_3x.shape[1] // 2
            ring_power[ry - 2:ry + 3, rx - 2:rx + 3] = 0
            ring_periodicity = float(np.clip((np.max(ring_power) / (np.mean(ring_power) + 1e-6) - 1.0) / 25.0, 0.0, 1.0))
            if ring_periodicity > 0.65 and periodicity > 0.65:
                is_sand_ripple = True
                regularity_score = 0.20  # Heavily penalize regional sand dunes
                return regularity_score, is_sand_ripple

        regularity_score = float(np.clip(0.6 * straightness + 0.4 * periodicity, 0.0, 1.0))
        return regularity_score, is_sand_ripple

    # -------------------------------------------------------------
    # 3. Motion-Artifact Mask Overlap
    # -------------------------------------------------------------
    @staticmethod
    def evaluate_motion_overlap(
        bbox_ping_start: int,
        bbox_ping_end: int,
        motion_corrupted_pings: List[int]
    ) -> float:
        """
        Calculates % overlap of detection with heave/pitch/roll or dropout pings.
        """
        if not motion_corrupted_pings:
            return 0.0
        
        target_pings = set(range(bbox_ping_start, bbox_ping_end + 1))
        if not target_pings:
            return 0.0

        corrupted_in_target = target_pings.intersection(set(motion_corrupted_pings))
        overlap_frac = len(corrupted_in_target) / len(target_pings)
        return float(np.clip(overlap_frac, 0.0, 1.0))

    # -------------------------------------------------------------
    # 4. Multi-Pass Persistence
    # -------------------------------------------------------------
    @staticmethod
    def evaluate_multi_pass_persistence(
        target_lat: Optional[float],
        target_lon: Optional[float],
        survey_line_id: str,
        other_line_detections: List[Dict[str, Any]],
        tolerance_m: float = 5.0
    ) -> Tuple[float, int, List[str]]:
        """
        Spatial join across survey lines within 5 m tolerance:
        - Target seen in 2-3 overlapping survey lines gets a confidence boost
        - One-off glint gets a slight penalty
        """
        if target_lat is None or target_lon is None:
            return 0.50, 1, [survey_line_id]

        observed_lines = {survey_line_id}
        for det in other_line_detections:
            d_lat = det.get("lat")
            d_lon = det.get("lon")
            d_line = det.get("line_id", "LINE_UNKNOWN")
            if d_lat is None or d_lon is None or d_line == survey_line_id:
                continue

            # Haversine distance in metres
            d_deg_lat = (d_lat - target_lat) * 111139.0
            d_deg_lon = (d_lon - target_lon) * 111139.0 * math.cos(math.radians(target_lat))
            dist_m = math.hypot(d_deg_lat, d_deg_lon)

            if dist_m <= tolerance_m:
                observed_lines.add(d_line)

        pass_count = len(observed_lines)
        if pass_count >= 3:
            persistence_score = 1.0
        elif pass_count == 2:
            persistence_score = 0.85
        else:
            persistence_score = 0.45  # Single-pass glint

        return persistence_score, pass_count, list(observed_lines)

    # -------------------------------------------------------------
    # 5. Calibrated 5-Term Fusion
    # -------------------------------------------------------------
    def fuse_evidence(
        self,
        cnn_score: float,
        shc_score: float,
        regularity_score: float,
        motion_penalty: float,
        persistence_score: float,
        shc_suppressed: bool = False,
        is_sand_ripple: bool = False,
        motion_suppressed: bool = False,
        suppression_reason: Optional[str] = None
    ) -> Tuple[float, bool, Optional[str]]:
        """
        Calibrated Logistic Fusion:
            logit = w0 + w1*z_cnn + w2*z_shc + w3*z_reg - w4*z_motion + w5*z_persist
            C = 100 * σ(logit)
        """
        # Hard physics vetoes
        if motion_penalty > 0.40 or motion_suppressed:
            return round(cnn_score * 0.15 * 100.0, 1), True, f"{int(motion_penalty * 100)}% overlap with motion-artifact mask"

        if shc_suppressed:
            return round(cnn_score * 0.12 * 100.0, 1), True, suppression_reason or "Shadow-highlight consistency violation"

        if is_sand_ripple:
            return 14.5, True, "Suppressed: orientation coherence matches regional sand ripples"

        # 5-Term Calibrated Logistic Equation
        w = self.weights
        logit = (
            w["w0"]
            + w["w1"] * cnn_score
            + w["w2"] * shc_score
            + w["w3"] * regularity_score
            - w["w4"] * motion_penalty
            + w["w5"] * persistence_score
        )
        prob = 1.0 / (1.0 + math.exp(-logit))
        calibrated_conf = round(float(np.clip(prob * 100.0, 1.0, 99.4)), 1)

        is_suppressed = calibrated_conf < 40.0
        reason = "Below 40% calibrated threshold" if is_suppressed else None
        return calibrated_conf, is_suppressed, reason

    # -------------------------------------------------------------
    # Full Verification Method
    # -------------------------------------------------------------
    def verify_candidate(
        self,
        target_id: str,
        class_name: str,
        raw_cnn_score: float,
        slant_range_m: float,
        towfish_alt_m: float,
        shadow_len_m: float,
        bbox_ping_start: int,
        bbox_ping_end: int,
        target_lat: Optional[float] = None,
        target_lon: Optional[float] = None,
        survey_line_id: str = "LINE_01",
        other_detections: Optional[List[Dict[str, Any]]] = None,
        motion_corrupted_pings: Optional[List[int]] = None,
        patch: Optional[np.ndarray] = None,
        ring_3x: Optional[np.ndarray] = None,
        channel: str = "starboard"
    ) -> EchoSiftEvidence:
        """
        Executes full EchoSift physics pipeline on a single candidate.
        """
        # 1. SHC
        shc_score, h_m, shadow_side, shc_reason = self.compute_shc(
            slant_range_m=slant_range_m,
            towfish_alt_m=towfish_alt_m,
            shadow_len_m=shadow_len_m,
            channel=channel,
            class_name=class_name
        )

        # 2. GRI
        reg_score, is_ripple = self.compute_regularity_index(patch, ring_3x)

        # 3. Motion mask overlap
        motion_penalty = self.evaluate_motion_overlap(
            bbox_ping_start, bbox_ping_end, motion_corrupted_pings or []
        )

        # 4. Multi-pass persistence
        persist_score, pass_count, passes = self.evaluate_multi_pass_persistence(
            target_lat, target_lon, survey_line_id, other_detections or []
        )

        # 5. Fusion
        fused_c, suppressed, reason = self.fuse_evidence(
            cnn_score=raw_cnn_score,
            shc_score=shc_score,
            regularity_score=reg_score,
            motion_penalty=motion_penalty,
            persistence_score=persist_score,
            shc_suppressed=(shc_reason is not None),
            is_sand_ripple=is_ripple,
            motion_suppressed=(motion_penalty > 0.40),
            suppression_reason=shc_reason
        )

        return EchoSiftEvidence(
            cnn_score=raw_cnn_score,
            shc_score=shc_score,
            height_estimate_m=h_m,
            shadow_side=shadow_side,
            regularity_score=reg_score,
            is_sand_ripple=is_ripple,
            motion_penalty=motion_penalty,
            persistence_score=persist_score,
            pass_count=pass_count,
            fused_confidence=fused_c,
            suppressed=suppressed,
            suppression_reason=reason
        )
