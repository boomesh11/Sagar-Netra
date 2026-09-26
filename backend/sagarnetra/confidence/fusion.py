"""
SagarNetra Confidence — Hazard Confidence Fusion Engine.
Combines calibrated neural classification, acoustic physics verification,
net structural signature, observation quality, and multi-view persistence
into a single calibrated Hazard Confidence score C in [0, 100].
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple
import numpy as np


class HazardStatus(str, Enum):
    CONFIRMED_HAZARD = "CONFIRMED_HAZARD"           # C >= 60%
    SUSPECTED_HAZARD = "SUSPECTED_HAZARD"           # 35% <= C < 60%
    CONFUSER_REJECTED = "CONFUSER_REJECTED"         # Confuser class or C < 35%
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE" # Severe quality impairment / nadir


CLASS_SEVERITY: Dict[str, float] = {
    "ghost_net": 1.00,
    "wreck_debris": 0.90,
    "pipe": 0.85,
    "cylinder": 0.80,
    "rope_cable": 0.75,
    "trap_pot": 0.60,
    "rock_cluster": 0.05,
    "sand_ripple": 0.05,
    "seagrass": 0.05,
    "fish_school": 0.05,
}


@dataclass
class FusedConfidence:
    score: float                        # C in [0.0, 100.0]
    status: HazardStatus                # Triage classification
    priority: float                     # Operational removal priority score [0.0, 1.5]
    p_calibrated: float                 # Temperature-calibrated classifier probability [0, 1]
    q_obs: float                        # Observation quality [0, 1]
    v_phys: float                       # Physics verifier score [-1, +1]
    s_net: float                        # Net signature / structural evidence [0, 1]
    views: int                          # Multi-pass independent confirmations
    explanation: str                    # Human-readable breakdown for dashboard inspector


class ConfidenceFuser:
    """
    Fuses multi-modal evidence into the single calibrated Hazard Confidence metric.
    """
    def __init__(
        self,
        w0: float = -1.5,
        w_cal: float = 1.8,
        w_obs: float = 1.0,
        w_phys: float = 2.0,
        w_net: float = 1.5,
        w_views: float = 0.8,
    ):
        self.w0 = w0
        self.w_cal = w_cal
        self.w_obs = w_obs
        self.w_phys = w_phys
        self.w_net = w_net
        self.w_views = w_views

    def compute_hazard_confidence(
        self,
        class_name: str,
        calibrated_prob: float,
        v_phys: float,
        q_obs: float = 1.0,
        s_net: float = 0.0,
        views: int = 1,
        r95_m: float = 3.0,
        in_sensitive_zone: bool = False,
    ) -> FusedConfidence:
        """
        Fuses terms according to:
          C = 100 * sigmoid(w0 + w_cal*logit(p_cal) + w_obs*Q_obs + w_phys*V_phys + w_net*S_net + w_views*min(views, 3))
        """
        eps = 1e-4
        p_safe = np.clip(calibrated_prob, eps, 1.0 - eps)
        logit_p = float(np.log(p_safe / (1.0 - p_safe)))
        logit_p = float(np.clip(logit_p, -6.0, 6.0))

        v_phys_safe = float(np.clip(v_phys, -1.0, 1.0))
        q_obs_safe = float(np.clip(q_obs, 0.0, 1.0))
        s_net_safe = float(np.clip(s_net, 0.0, 1.0))
        views_term = float(min(max(views, 1), 3))

        z = (
            self.w0
            + self.w_cal * logit_p
            + self.w_obs * q_obs_safe
            + self.w_phys * v_phys_safe
            + self.w_net * s_net_safe
            + self.w_views * views_term
        )

        # Sigmoid to [0, 100]
        c_score = float(100.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0))))
        c_score = round(c_score, 1)

        # Determine status
        is_confuser = class_name in ["rock_cluster", "sand_ripple", "seagrass", "fish_school"]
        if q_obs_safe < 0.25:
            status = HazardStatus.INSUFFICIENT_EVIDENCE
        elif is_confuser or c_score < 35.0:
            status = HazardStatus.CONFUSER_REJECTED
        elif c_score >= 60.0:
            status = HazardStatus.CONFIRMED_HAZARD
        else:
            status = HazardStatus.SUSPECTED_HAZARD

        # Calculate Priority = (C / 100) * severity(class) * (1 / (1 + r95 / 10)) * (1.5 if sensitive)
        base_sev = CLASS_SEVERITY.get(class_name, 0.5)
        pos_attenuation = 1.0 / (1.0 + (r95_m / 10.0))
        priority = (c_score / 100.0) * base_sev * pos_attenuation
        if in_sensitive_zone:
            priority *= 1.5
        priority = round(float(priority), 3)

        explanation = (
            f"Hazard Confidence {c_score:.1f}% [{status.value}] | "
            f"p_cal={calibrated_prob:.2f}, V_phys={v_phys:.2f}, Q_obs={q_obs:.2f}, "
            f"S_net={s_net:.2f}, Views={views}, Priority={priority:.3f}"
        )

        return FusedConfidence(
            score=c_score,
            status=status,
            priority=priority,
            p_calibrated=round(calibrated_prob, 3),
            q_obs=round(q_obs_safe, 3),
            v_phys=round(v_phys_safe, 3),
            s_net=round(s_net_safe, 3),
            views=int(views),
            explanation=explanation,
        )
