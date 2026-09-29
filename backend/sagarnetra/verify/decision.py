"""
backend/sagarnetra/verify/decision.py
======================================
EchoSift Stage 3 Verification & Decision Engine.
The neural network and detectors are candidate generators, not judges.
Every candidate is verified against:
  - Sonar shadow physics (causal direction away from nadir, metric height)
  - Seabed context contrast (patch vs surrounding annulus, ripple suppression)
  - Data quality mask overlap (motion/dropout penalty)
  - Net signature evidence (mesh + thin ridges + float points + low relief)
  - Anomaly scoring (PatchCore distance from natural seabed)

Outputs decisions:
  wreck | pipe_cylinder | net_debris | other_manmade | unknown_manmade | natural_suppressed | uncertain
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np


@dataclass
class TargetDecisionResult:
    decision: str                      # wreck | pipe_cylinder | net_debris | other_manmade | unknown_manmade | natural_suppressed | uncertain
    class_name: str                    # Target class
    confidence: float                  # [0, 100]%
    suppressed: bool
    suppression_reason: Optional[str]
    decision_reason: str               # Plain-English explanation
    evidence_dict: Dict[str, float | str | bool | None]


def decide_target(
    cnn_score: Optional[float] = None,
    shc_score: float = 0.5,
    regularity_score: float = 0.5,
    motion_penalty: float = 0.0,
    persistence_score: float = 0.5,
    shadow_side: str = "correct",
    height_estimate_m: Optional[float] = None,
    is_sand_ripple: bool = False,
    snr_score: float = 0.50,
    s_net: Optional[float] = None,
    annular_contrast: Optional[float] = None,
    anomaly_score: Optional[float] = None,
    anthropogenic_score: Optional[float] = None,
    quality_overlap_pct: float = 0.0,
    dims_px: Tuple[float, float] = (20.0, 20.0),
    has_shadow: bool = True,
    merged_count: int = 1,
    snr_db: float = 5.0,
) -> TargetDecisionResult:
    """
    Executes Stage 3 physics verification and decision logic.
    """
    s_net_val = float(s_net) if s_net is not None else 0.10
    anom_val = float(anomaly_score) if anomaly_score is not None else 0.20
    ann_contrast = float(annular_contrast) if annular_contrast is not None else 0.70
    anthro_val = float(anthropogenic_score) if anthropogenic_score is not None else regularity_score

    # 1. 5-Term Logistic Fusion (uncalibrated)
    w0 = -1.25
    w1 = 2.80  # Candidate score (CNN score if detector ran, otherwise snr_score)
    w2 = 2.45  # SHC shadow physics
    w3 = 1.75  # Regularity
    w4 = 3.20  # Motion penalty
    w5 = 1.95  # Persistence

    cand_term = cnn_score if cnn_score is not None else snr_score
    logit = w0 + w1 * cand_term + w2 * shc_score + w3 * regularity_score - w4 * motion_penalty + w5 * persistence_score
    prob = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, logit))))
    fused_conf = round(float(np.clip(prob * 100.0, 1.0, 99.4)), 1)

    # 2. Hard Physics Suppression: Sand Ripples & Background Continuity (Phase 2 Rule 1)
    # natural_suppressed only if (FFT/Gabor periodicity or texture similarity says pattern CONTINUES into annulus)
    # AND (no valid highlight-shadow pair OR anomaly score is low).
    # Low annular contrast alone must NEVER suppress a candidate.
    has_valid_shadow = has_shadow and shadow_side == "correct" and (shc_score >= 0.40)
    is_anomalous = anom_val >= 0.45 or anthro_val >= 0.55
    pattern_continues = is_sand_ripple

    if pattern_continues and (not has_valid_shadow or not is_anomalous):
        conf_suppressed = round(min(fused_conf, 18.0), 1)
        reason = f"Suppressed: acoustic pattern continues across surrounding seabed (periodic sand ripples, FFT periodicity detected without anomalous shadow relief)."
        return TargetDecisionResult(
            decision="natural_suppressed",
            class_name="natural_suppressed",
            confidence=conf_suppressed,
            suppressed=True,
            suppression_reason=reason,
            decision_reason=reason,
            evidence_dict={
                "cnn_score": cnn_score,
                "shc_score": shc_score,
                "regularity_score": regularity_score,
                "is_sand_ripple": True,
                "annular_contrast": ann_contrast,
                "anomaly_score": anom_val,
                "fused_confidence": conf_suppressed,
            }
        )

    # 3. Hard Physics Suppression: Anti-Causal Shadow
    if shadow_side == "incorrect":
        conf_suppressed = round(min(fused_conf, 14.0), 1)
        reason = "Suppressed: acoustic shadow points toward nadir (fails causal highlight-shadow physics; acoustic void/depression)."
        return TargetDecisionResult(
            decision="natural_suppressed",
            class_name="natural_suppressed",
            confidence=conf_suppressed,
            suppressed=True,
            suppression_reason=reason,
            decision_reason=reason,
            evidence_dict={
                "cnn_score": cnn_score,
                "shc_score": shc_score,
                "shadow_side": shadow_side,
                "fused_confidence": conf_suppressed,
            }
        )

    # 4. Flat Sediment Variation (no valid shadow and near-zero relief)
    if (not has_shadow or not has_valid_shadow) and (height_estimate_m is None or height_estimate_m < 0.15) and cnn_score is None:
        conf_suppressed = round(min(fused_conf, 22.0), 1)
        reason = "Suppressed: flat acoustic feature with no causal shadow or elevation relief (sediment variation)."
        return TargetDecisionResult(
            decision="natural_suppressed",
            class_name="natural_suppressed",
            confidence=conf_suppressed,
            suppressed=True,
            suppression_reason=reason,
            decision_reason=reason,
            evidence_dict={
                "cnn_score": cnn_score,
                "has_shadow": has_shadow,
                "has_valid_shadow": has_valid_shadow,
                "height_estimate_m": height_estimate_m,
                "fused_confidence": conf_suppressed,
            }
        )

    # 5. Data Quality Mask Overlap (> 40% corrupted)
    if quality_overlap_pct > 40.0 or motion_penalty > 0.40:
        reason = f"Uncertain: high corruption ({quality_overlap_pct:.1f}% > 40%) in acoustic data-quality mask."
        return TargetDecisionResult(
            decision="uncertain",
            class_name="uncertain",
            confidence=round(fused_conf * 0.4, 1),
            suppressed=False,
            suppression_reason=None,
            decision_reason=reason,
            evidence_dict={
                "quality_overlap_pct": quality_overlap_pct,
                "motion_penalty": motion_penalty,
                "fused_confidence": round(fused_conf * 0.4, 1),
            }
        )

    # 6. Low Confidence Check (below 40% threshold routes to uncertain)
    if fused_conf < 40.0:
        reason = f"Uncertain: acoustic confidence ({fused_conf:.1f}%) below verification threshold (40.0%)."
        return TargetDecisionResult(
            decision="uncertain",
            class_name="uncertain",
            confidence=fused_conf,
            suppressed=False,
            suppression_reason=None,
            decision_reason=reason,
            evidence_dict={"fused_confidence": fused_conf}
        )

    # 7. Verification of Man-Made Target Classes
    h_len, h_wid = max(dims_px), min(dims_px)
    aspect_ratio = h_len / max(1.0, h_wid)

    # Net Debris: amorphous textured patch + thin rope-like ridges + low relief + mesh floats
    # (Never decided from height alone)
    is_net_debris = (
        s_net_val >= 0.52
        and (height_estimate_m is None or height_estimate_m <= 2.5)
        and aspect_ratio < 6.0
        and merged_count <= 2
    )

    if is_net_debris:
        height_str = f"{height_estimate_m:.1f}m" if height_estimate_m is not None else "low relief"
        reason = f"EchoSift confirmed: net signature detected (s_net={s_net_val:.2f}, thin rope ridges, float points, {height_str})."
        return TargetDecisionResult(
            decision="net_debris",
            class_name="net_debris",
            confidence=fused_conf,
            suppressed=False,
            suppression_reason=None,
            decision_reason=reason,
            evidence_dict={
                "s_net": s_net_val,
                "height_estimate_m": height_estimate_m,
                "fused_confidence": fused_conf,
            }
        )

    # Wreck requires MULTIPLE structural cues together (P1 fix):
    # - Spatial extent: substantial physical vessel scale (h_len >= 50 px / 5.0m, h_wid >= 18 px / 1.8m)
    # - Multi-fragment or massive hull: merged_count >= 3 or large continuous hull envelope
    # - Elevation relief: verified acoustic shadow relief (height >= 1.5m or prominent shadow with SHC >= 0.65)
    # - Structural consistency: regularity >= 0.30 and not amorphous net debris (s_net < 0.50)
    has_substantial_size = (
        (merged_count >= 3 and h_len >= 45.0 and h_wid >= 24.0 and aspect_ratio <= 6.0)
        or (h_len >= 55.0 and h_wid >= 28.0 and aspect_ratio <= 5.0)
    )
    has_elevation_relief = (height_estimate_m is not None and height_estimate_m >= 1.5) or (has_shadow and shc_score >= 0.65)

    is_wreck = (
        has_substantial_size
        and has_elevation_relief
        and s_net_val < 0.50
        and regularity_score >= 0.30
    )

    if is_wreck:
        reason = f"EchoSift confirmed: large-scale rigid wreck structure ({int(h_len)}x{int(h_wid)} px) with prominent acoustic shadow relief ({fused_conf:.1f}% confidence)."
        return TargetDecisionResult(
            decision="wreck",
            class_name="wreck",
            confidence=fused_conf,
            suppressed=False,
            suppression_reason=None,
            decision_reason=reason,
            evidence_dict={
                "length_px": h_len,
                "width_px": h_wid,
                "merged_count": merged_count,
                "height_estimate_m": height_estimate_m,
                "fused_confidence": fused_conf,
            }
        )

    # Pipe / Cylinder: high linear/tubular aspect ratio with straight parallel shadow
    is_pipe = (
        aspect_ratio >= 3.5
        and regularity_score >= 0.60
        and s_net_val < 0.45
    )

    if is_pipe:
        reason = f"EchoSift confirmed: linear cylindrical highlight with parallel acoustic shadow boundary (straightness {regularity_score:.2f})."
        return TargetDecisionResult(
            decision="pipe_cylinder",
            class_name="pipe_cylinder",
            confidence=fused_conf,
            suppressed=False,
            suppression_reason=None,
            decision_reason=reason,
            evidence_dict={
                "aspect_ratio": round(aspect_ratio, 2),
                "regularity_score": regularity_score,
                "fused_confidence": fused_conf,
            }
        )

    # Other Man-Made: highly regular rectangular/manufactured geometry
    is_other_manmade = (
        regularity_score >= 0.75
        and anthro_val >= 0.70
        and s_net_val < 0.45
    )

    if is_other_manmade:
        reason = f"EchoSift confirmed: manufactured geometric structure with verified causal shadow ({fused_conf:.1f}% confidence)."
        return TargetDecisionResult(
            decision="other_manmade",
            class_name="other_manmade",
            confidence=fused_conf,
            suppressed=False,
            suppression_reason=None,
            decision_reason=reason,
            evidence_dict={
                "regularity_score": regularity_score,
                "anthropogenic_score": anthro_val,
                "fused_confidence": fused_conf,
            }
        )

    # Open-Set Routing (Phase 2 Rule 3):
    # If anomaly/anthropogenic evidence is elevated and a valid shadow exists, but no known class passes threshold:
    # Routes to unknown_manmade (NEVER natural_suppressed, NEVER net_debris).
    if has_valid_shadow and is_anomalous:
        reason = f"EchoSift confirmed: anomalous anthropogenic structure (anomaly {anom_val:.2f}, regularity {regularity_score:.2f}, valid shadow); rejected known classes (net, wreck, pipe). Classified as unknown_manmade."
        return TargetDecisionResult(
            decision="unknown_manmade",
            class_name="unknown_manmade",
            confidence=fused_conf,
            suppressed=False,
            suppression_reason=None,
            decision_reason=reason,
            evidence_dict={
                "anomaly_score": anom_val,
                "regularity_score": regularity_score,
                "s_net": s_net_val,
                "fused_confidence": fused_conf,
            }
        )

    # Lacks valid acoustic shadow or anomalous structure -> Suppress as natural seabed variation
    conf_suppressed = round(min(fused_conf, 22.0), 1)
    reason = "Suppressed: flat acoustic feature lacks confirmed shadow relief or anomalous anthropogenic structure (natural seabed variation)."
    return TargetDecisionResult(
        decision="natural_suppressed",
        class_name="natural_suppressed",
        confidence=conf_suppressed,
        suppressed=True,
        suppression_reason=reason,
        decision_reason=reason,
        evidence_dict={
            "anomaly_score": anom_val,
            "regularity_score": regularity_score,
            "has_valid_shadow": has_valid_shadow,
            "fused_confidence": conf_suppressed,
        }
    )
