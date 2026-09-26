"""
SagarNetra Geotagging — 5-Component Position Error Budget.
Computes the 95% circular error probable radius (r95) from:
  - GPS receiver variance (sigma_gps)
  - Layback cable model uncertainty (sigma_L)
  - Compass heading variance scaled by range (x * sigma_theta)
  - Slant-range / across-track resolution (sigma_x)
  - Timing jitter scaled by vessel speed (v * sigma_t)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict


@dataclass
class PositionErrorBudget:
    r95_m: float                  # 95% Circular Error Probable radius (metres)
    sigma_total_m: float          # Combined 1-sigma uncertainty (metres)
    sigma_gps_m: float            # GPS receiver error
    sigma_layback_m: float        # Cable payout & catenary model error
    sigma_heading_m: float        # Angular compass error at target range (x * sigma_theta)
    sigma_range_m: float          # Acoustic sample resolution
    sigma_timing_m: float         # Latency jitter at vessel speed (v * sigma_t)

    def to_dict(self) -> Dict[str, float]:
        return {
            "r95_m": round(self.r95_m, 2),
            "sigma_total_m": round(self.sigma_total_m, 2),
            "sigma_gps_m": round(self.sigma_gps_m, 2),
            "sigma_layback_m": round(self.sigma_layback_m, 2),
            "sigma_heading_m": round(self.sigma_heading_m, 2),
            "sigma_range_m": round(self.sigma_range_m, 2),
            "sigma_timing_m": round(self.sigma_timing_m, 2),
        }


def compute_position_error_budget(
    ground_range_m: float,
    layback_m: float,
    speed_mps: float = 1.5,
    sigma_gps_m: float = 2.0,            # Standard DGPS
    sigma_heading_deg: float = 1.0,       # Towfish magnetic/fluxgate compass
    sigma_range_m: float = 0.15,          # Slant-to-ground range discretization
    sigma_timing_s: float = 0.10,         # PPS sync jitter
) -> PositionErrorBudget:
    """
    Computes rigorous position error budget:
        sigma_tot^2 = sigma_gps^2 + sigma_L^2 + (x * sigma_theta)^2 + sigma_x^2 + (v * sigma_t)^2
        r95 = 2.45 * sigma_tot
    """
    # Layback uncertainty: 0.10 * L + 1.0 m (catenary sag & cable angle model)
    sigma_layback_m = 0.10 * layback_m + 1.0

    # Heading error across-track: x * sin(sigma_theta) ~ x * sigma_theta_rad
    sigma_theta_rad = math.radians(sigma_heading_deg)
    sigma_heading_m = ground_range_m * sigma_theta_rad

    # Timing latency along-track: v * sigma_t
    sigma_timing_m = speed_mps * sigma_timing_s

    # Quadratic sum
    variance_total = (
        sigma_gps_m**2
        + sigma_layback_m**2
        + sigma_heading_m**2
        + sigma_range_m**2
        + sigma_timing_m**2
    )
    sigma_total = math.sqrt(variance_total)

    # 95% circular error radius factor for 2D Rayleigh distribution: sqrt(-2 * ln(0.05)) = 2.4477 ~ 2.45
    r95 = 2.45 * sigma_total

    return PositionErrorBudget(
        r95_m=round(r95, 2),
        sigma_total_m=round(sigma_total, 2),
        sigma_gps_m=round(sigma_gps_m, 2),
        sigma_layback_m=round(sigma_layback_m, 2),
        sigma_heading_m=round(sigma_heading_m, 2),
        sigma_range_m=round(sigma_range_m, 2),
        sigma_timing_m=round(sigma_timing_m, 2),
    )
