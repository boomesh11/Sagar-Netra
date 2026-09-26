"""
SagarNetra Verification — Eight Acoustic Physics Rules (R1 to R8).
Assesses candidates against acoustic geometry and propagation physics:
  - R1: Class height prior
  - R2: Highlight before shadow (causal direction)
  - R3: Port/starboard crosstalk mirror check
  - R4: Along-track beam persistence
  - R5: Water column / pre-bottom echo rejection
  - R6: Nadir blind zone and surface multipath band rejection
  - R7: Beam footprint resolution adequacy
  - R8: Local seabed slope reliability
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, List, Optional, Tuple


@dataclass
class RuleResult:
    rule_id: str
    name: str
    score: int   # +1: consistent, 0: not assessable / neutral, -1: inconsistent
    reason: str


@dataclass
class VerificationResult:
    v_phys: float               # Raw score in [-1.0, 1.0] (mean of rule scores)
    v_phys_norm: float          # Mapped score in [0.0, 1.0] for confidence fusion
    computed_height_m: Optional[float]
    passed: bool                # True if v_phys >= 0.0 and no hard physics violation
    rule_results: List[RuleResult] = field(default_factory=list)
    summary_log: str = ""


# Class height expectations [min_m, max_m]
CLASS_HEIGHT_PRIORS: Dict[str, Tuple[float, float]] = {
    "ghost_net": (0.0, 1.5),
    "rope_cable": (0.0, 0.35),
    "pipe": (0.08, 1.5),
    "cylinder": (0.15, 2.0),
    "wreck_debris": (0.4, 15.0),
    "trap_pot": (0.2, 1.3),
    "rock_cluster": (0.1, 4.0),
    "sand_ripple": (0.02, 0.6),
    "seagrass": (0.05, 1.2),
    "fish_school": (0.1, 10.0),
}


def calculate_height_from_shadow(
    altitude_m: float,
    ground_range_m: float,
    shadow_length_m: float,
) -> float:
    """
    Computes physical target height from acoustic shadow geometry:
        h = (H * L_s) / (x_0 + L_s)
    """
    if altitude_m <= 0.0 or ground_range_m <= 0.0 or shadow_length_m <= 0.0:
        return 0.0
    h = (altitude_m * shadow_length_m) / (ground_range_m + shadow_length_m)
    return max(0.0, float(h))


class PhysicsVerifier:
    """
    Eight-rule acoustic physics verification engine.
    """
    def __init__(self, horizontal_beamwidth_deg: float = 0.4):
        self.beamwidth_rad = math.radians(horizontal_beamwidth_deg)

    def verify(
        self,
        class_name: str,
        ground_range_m: float,
        altitude_m: float,
        slant_range_m: float,
        channel: str = "stbd",
        highlight_extent_m: float = 1.0,
        shadow_length_m: Optional[float] = None,
        shadow_range_m: Optional[float] = None,
        pings_persisted: int = 3,
        local_slope_deg: float = 1.0,
        mirror_detected: bool = False,
    ) -> VerificationResult:
        rules: List[RuleResult] = []

        # Compute object height from shadow if shadow exists
        has_shadow = shadow_length_m is not None and shadow_length_m > 0.05
        computed_h: Optional[float] = None
        if has_shadow:
            computed_h = calculate_height_from_shadow(altitude_m, ground_range_m, shadow_length_m)

        # ----------------------------------------------------
        # R1: Class Height Prior
        # ----------------------------------------------------
        priors = CLASS_HEIGHT_PRIORS.get(class_name, (0.0, 5.0))
        if computed_h is not None:
            min_h, max_h = priors
            if min_h <= computed_h <= max_h:
                rules.append(RuleResult(
                    "R1", "Class Height Prior", +1,
                    f"Height {computed_h:.2f} m matches expected {class_name} envelope [{min_h:.1f}, {max_h:.1f}] m."
                ))
            elif computed_h > max_h * 1.5:
                rules.append(RuleResult(
                    "R1", "Class Height Prior", -1,
                    f"Height {computed_h:.2f} m exceeds realistic {class_name} maximum {max_h:.1f} m."
                ))
            else:
                rules.append(RuleResult(
                    "R1", "Class Height Prior", 0,
                    f"Height {computed_h:.2f} m slightly outside typical range [{min_h:.1f}, {max_h:.1f}] m."
                ))
        else:
            # Ghost nets and flat ropes often cast no measurable acoustic shadow
            if class_name in ["ghost_net", "rope_cable", "sand_ripple"]:
                rules.append(RuleResult(
                    "R1", "Class Height Prior", +1,
                    f"Flat target ({class_name}) without prominent shadow is physically consistent."
                ))
            else:
                rules.append(RuleResult(
                    "R1", "Class Height Prior", 0,
                    f"No measurable shadow for {class_name}; height unassessed."
                ))

        # ----------------------------------------------------
        # R2: Highlight Before Shadow (Causal Ray Order)
        # ----------------------------------------------------
        if shadow_range_m is not None and has_shadow:
            if shadow_range_m > ground_range_m:
                rules.append(RuleResult(
                    "R2", "Highlight Before Shadow", +1,
                    f"Shadow ({shadow_range_m:.1f} m) on far-range side of highlight ({ground_range_m:.1f} m)."
                ))
            else:
                rules.append(RuleResult(
                    "R2", "Highlight Before Shadow", -1,
                    f"Anti-causal shadow! Shadow ({shadow_range_m:.1f} m) closer to nadir than highlight ({ground_range_m:.1f} m); likely seabed depression or artefact."
                ))
        else:
            rules.append(RuleResult(
                "R2", "Highlight Before Shadow", 0,
                "No shadow pairing assessable."
            ))

        # ----------------------------------------------------
        # R3: Port/Starboard Mirror (Crosstalk Check)
        # ----------------------------------------------------
        if mirror_detected:
            rules.append(RuleResult(
                "R3", "Port/Starboard Mirror", -1,
                f"Symmetric return detected at range {ground_range_m:.1f} m on opposite channel; electrical crosstalk or surface multipath."
            ))
        else:
            rules.append(RuleResult(
                "R3", "Port/Starboard Mirror", +1,
                "No symmetric opposite-channel echo detected."
            ))

        # ----------------------------------------------------
        # R4: Along-Track Persistence
        # ----------------------------------------------------
        if pings_persisted >= 2:
            rules.append(RuleResult(
                "R4", "Along-track Persistence", +1,
                f"Candidate persists over {pings_persisted} pings, confirming spatial coherence."
            ))
        else:
            rules.append(RuleResult(
                "R4", "Along-track Persistence", -1,
                "Candidate isolated to a single ping; transient acoustic spike or speckle noise."
            ))

        # ----------------------------------------------------
        # R5: Water Column Rejection
        # ----------------------------------------------------
        if altitude_m > 0.5 and slant_range_m < (altitude_m * 0.95):
            rules.append(RuleResult(
                "R5", "Water Column Rejection", -1,
                f"Slant range ({slant_range_m:.1f} m) < altitude ({altitude_m:.1f} m); suspended echo in water column."
            ))
        else:
            rules.append(RuleResult(
                "R5", "Water Column Rejection", +1,
                f"Echo at or beyond bottom arrival (slant range {slant_range_m:.1f} m >= {altitude_m:.1f} m)."
            ))

        # ----------------------------------------------------
        # R6: Nadir and Surface Multipath Bands
        # ----------------------------------------------------
        # Nadir band: within 1m of nadir
        # Surface multipath: slant range approx 2 * altitude
        is_nadir = ground_range_m < 1.0
        is_multipath = (altitude_m > 2.0) and abs(slant_range_m - 2.0 * altitude_m) < 0.8
        if is_nadir:
            rules.append(RuleResult(
                "R6", "Nadir & Multipath Band", -1,
                f"Target at ground range {ground_range_m:.1f} m inside nadir blind zone."
            ))
        elif is_multipath:
            rules.append(RuleResult(
                "R6", "Nadir & Multipath Band", -1,
                f"Slant range {slant_range_m:.1f} m matches ~2x altitude ({altitude_m:.1f} m); surface bounce ghost."
            ))
        else:
            rules.append(RuleResult(
                "R6", "Nadir & Multipath Band", +1,
                "Outside nadir blind zone and surface multipath bands."
            ))

        # ----------------------------------------------------
        # R7: Resolution Adequacy
        # ----------------------------------------------------
        # Beam footprint = ground_range * beamwidth_rad
        footprint_m = max(0.15, ground_range_m * self.beamwidth_rad)
        if highlight_extent_m >= (2.5 * footprint_m):
            rules.append(RuleResult(
                "R7", "Resolution Adequacy", +1,
                f"Extent {highlight_extent_m:.2f} m spans >= 2.5 beam footprints ({footprint_m:.2f} m)."
            ))
        elif highlight_extent_m >= (1.0 * footprint_m):
            rules.append(RuleResult(
                "R7", "Resolution Adequacy", 0,
                f"Extent {highlight_extent_m:.2f} m spans marginal beam footprint ({footprint_m:.2f} m)."
            ))
        else:
            rules.append(RuleResult(
                "R7", "Resolution Adequacy", -1,
                f"Extent {highlight_extent_m:.2f} m below single beam footprint ({footprint_m:.2f} m); insufficient resolution."
            ))

        # ----------------------------------------------------
        # R8: Local Seabed Slope
        # ----------------------------------------------------
        if local_slope_deg <= 5.0:
            rules.append(RuleResult(
                "R8", "Local Seabed Slope", +1,
                f"Seabed slope {local_slope_deg:.1f} deg <= 5.0 deg; planar acoustic geometry valid."
            ))
        elif local_slope_deg <= 12.0:
            rules.append(RuleResult(
                "R8", "Local Seabed Slope", 0,
                f"Moderate seabed slope {local_slope_deg:.1f} deg; height estimate geometry degraded."
            ))
        else:
            rules.append(RuleResult(
                "R8", "Local Seabed Slope", -1,
                f"Excessive slope {local_slope_deg:.1f} deg > 12.0 deg; severe topographic shadow distortion."
            ))

        # Overall physics score
        v_phys = float(sum(r.score for r in rules) / len(rules))
        # Map [-1, 1] -> [0, 1]
        v_phys_norm = float(max(0.0, min(1.0, (v_phys + 1.0) / 2.0)))

        # Fail if hard rejection (R2 anti-causal or R3 mirror or R5 water column) or v_phys < -0.1
        hard_fail = any(r.score == -1 for r in rules if r.rule_id in ["R2", "R3", "R5", "R6"])
        passed = (not hard_fail) and (v_phys >= -0.1)

        summary_parts = [f"{r.rule_id}: {r.name} -> {r.score:+d} ({r.reason})" for r in rules]
        summary_log = "\n".join(summary_parts)

        return VerificationResult(
            v_phys=round(v_phys, 3),
            v_phys_norm=round(v_phys_norm, 3),
            computed_height_m=round(computed_h, 3) if computed_h is not None else None,
            passed=passed,
            rule_results=rules,
            summary_log=summary_log,
        )
