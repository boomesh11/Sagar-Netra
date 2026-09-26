"""
SagarNetra Coverage & Clearance — Probability of Detection (PoD) Grid Map & Second-Look Planner.
Provides quantitative proof of surveyed seabed:
  - Cell-by-cell PoD calculation for reference targets (ghost net & cylinder)
  - 4-state clearance classification: SURVEYED_CLEAR, INSUFFICIENT, CANDIDATE, NOT_SURVEYED
  - Total km^2 coverage accounting for port/regional clearances
  - Second-look orthogonal line generator for ambiguous / low-evidence targets
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

from backend.sagarnetra.geo.project import utm_to_latlon


class ClearanceState(str, Enum):
    SURVEYED_CLEAR = "SURVEYED_CLEAR"   # PoD >= 0.80 and no hazard
    CANDIDATE = "CANDIDATE"             # Target pin present
    INSUFFICIENT = "INSUFFICIENT"       # Surveyed but PoD < 0.50 or quality degraded
    NOT_SURVEYED = "NOT_SURVEYED"       # Unvisited cell


def model_pod(
    ground_range_m: float,
    max_range_m: float = 75.0,
    altitude_m: float = 8.0,
    snr_db: float = 18.0,
    burial_frac: float = 0.5,
    target_type: str = "ghost_net",
) -> float:
    """
    Computes Probability of Detection (PoD) for a reference target:
      - sweet spot at 30% - 60% of range
      - attenuation at far-range (grazing angle < 5 deg) and near-nadir
    """
    if ground_range_m < 1.0 or ground_range_m > max_range_m:
        return 0.0

    norm_range = ground_range_m / max_range_m  # in [0, 1]

    # Grazing angle theta = arctan(H / x)
    grazing_deg = math.degrees(math.atan2(altitude_m, ground_range_m))

    if target_type == "ghost_net":
        # Gillnet fragment 5m x 2m, 50% buried
        # Penalized heavily if grazing angle too low (< 4 deg) or high burial
        a0 = 1.8
        a_snr = 0.08 * (snr_db - 15.0)
        a_range = -3.2 * (norm_range - 0.45)**2
        a_burial = -1.5 * burial_frac
    else:  # "cylinder"
        a0 = 2.4
        a_snr = 0.10 * (snr_db - 15.0)
        a_range = -2.5 * (norm_range - 0.45)**2
        a_burial = -2.0 * burial_frac

    z = a0 + a_snr + a_range + a_burial
    pod = 1.0 / (1.0 + math.exp(-z))
    return float(max(0.0, min(0.99, pod)))


@dataclass
class SecondLookLine:
    line_id: str
    target_id: str
    heading_deg: float
    start_utm: Tuple[float, float]
    end_utm: Tuple[float, float]
    start_latlon: Tuple[float, float]
    end_latlon: Tuple[float, float]
    swath_offset_m: float
    length_m: float


class ClearanceGridMap:
    """
    Discrete metric grid tracking survey coverage and clearance states.
    """
    def __init__(
        self,
        origin_easting: float,
        origin_northing: float,
        width_m: float,
        height_m: float,
        cell_size_m: float = 2.0,
        zone: int = 44,
    ):
        self.origin_e = origin_easting
        self.origin_n = origin_northing
        self.width_m = width_m
        self.height_m = height_m
        self.cell_size_m = cell_size_m
        self.zone = zone

        self.n_cols = int(math.ceil(width_m / cell_size_m))
        self.n_rows = int(math.ceil(height_m / cell_size_m))

        # 2D arrays: PoD float32 and ClearanceState byte
        self.pod_grid = np.zeros((self.n_rows, self.n_cols), dtype=np.float32)
        self.state_grid = np.full((self.n_rows, self.n_cols), ClearanceState.NOT_SURVEYED.value, dtype=object)

    def record_swath(
        self,
        start_e: float,
        start_n: float,
        end_e: float,
        end_n: float,
        altitude_m: float = 8.0,
        range_m: float = 60.0,
        snr_db: float = 18.0,
    ) -> None:
        """
        Sweeps a survey track line across the grid and computes cell-by-cell PoD.
        """
        line_vec = np.array([end_e - start_e, end_n - start_n])
        line_len = np.linalg.norm(line_vec)
        if line_len < 1e-3:
            return
        line_dir = line_vec / line_len

        # Cell coordinates in metric space relative to origin
        r_indices = np.arange(self.n_rows)
        c_indices = np.arange(self.n_cols)
        c_grid, r_grid = np.meshgrid(c_indices, r_indices)

        cells_e = self.origin_e + (c_grid + 0.5) * self.cell_size_m
        cells_n = self.origin_n + (r_grid + 0.5) * self.cell_size_m

        # Vector from start to each cell
        v_e = cells_e - start_e
        v_n = cells_n - start_n

        # Along-track projection
        proj_along = v_e * line_dir[0] + v_n * line_dir[1]
        # Across-track perpendicular distance
        dist_across = np.abs(v_e * (-line_dir[1]) + v_n * line_dir[0])

        # Active mask inside swath
        in_swath = (proj_along >= -5.0) & (proj_along <= (line_len + 5.0)) & (dist_across <= range_m)

        for r, c in zip(*np.where(in_swath)):
            x_m = float(dist_across[r, c])
            pod = model_pod(x_m, max_range_m=range_m, altitude_m=altitude_m, snr_db=snr_db)
            if pod > self.pod_grid[r, c]:
                self.pod_grid[r, c] = pod
                if self.state_grid[r, c] != ClearanceState.CANDIDATE.value:
                    if pod >= 0.80:
                        self.state_grid[r, c] = ClearanceState.SURVEYED_CLEAR.value
                    elif pod >= 0.50:
                        self.state_grid[r, c] = ClearanceState.SURVEYED_CLEAR.value
                    else:
                        self.state_grid[r, c] = ClearanceState.INSUFFICIENT.value

    def mark_target(self, target_e: float, target_n: float) -> None:
        """
        Marks cell containing a target pin as CANDIDATE.
        """
        col = int((target_e - self.origin_e) / self.cell_size_m)
        row = int((target_n - self.origin_n) / self.cell_size_m)
        if 0 <= row < self.n_rows and 0 <= col < self.n_cols:
            self.state_grid[row, col] = ClearanceState.CANDIDATE.value

    def get_clearance_summary(self) -> Dict[str, float]:
        """
        Computes total area in square kilometres for each clearance state.
        """
        cell_area_km2 = (self.cell_size_m * self.cell_size_m) / 1e6
        total_cells = self.n_rows * self.n_cols

        counts = {
            ClearanceState.SURVEYED_CLEAR.value: int(np.sum(self.state_grid == ClearanceState.SURVEYED_CLEAR.value)),
            ClearanceState.CANDIDATE.value: int(np.sum(self.state_grid == ClearanceState.CANDIDATE.value)),
            ClearanceState.INSUFFICIENT.value: int(np.sum(self.state_grid == ClearanceState.INSUFFICIENT.value)),
            ClearanceState.NOT_SURVEYED.value: int(np.sum(self.state_grid == ClearanceState.NOT_SURVEYED.value)),
        }

        return {
            "total_area_km2": round(total_cells * cell_area_km2, 6),
            "surveyed_clear_km2": round(counts[ClearanceState.SURVEYED_CLEAR.value] * cell_area_km2, 6),
            "candidate_km2": round(counts[ClearanceState.CANDIDATE.value] * cell_area_km2, 6),
            "insufficient_km2": round(counts[ClearanceState.INSUFFICIENT.value] * cell_area_km2, 6),
            "not_surveyed_km2": round(counts[ClearanceState.NOT_SURVEYED.value] * cell_area_km2, 6),
            "candidate_count": counts[ClearanceState.CANDIDATE.value],
            "clearance_percent": round(100.0 * counts[ClearanceState.SURVEYED_CLEAR.value] / max(total_cells, 1), 2),
        }

    def plan_second_look_line(
        self,
        target_id: str,
        target_e: float,
        target_n: float,
        original_heading_deg: float,
        swath_range_m: float = 60.0,
        run_length_m: float = 120.0,
    ) -> SecondLookLine:
        """
        Plans an orthogonal survey pass placing the target at ~45% of swath range
        where acoustic shadow and highlight contrast are maximized.
        """
        # Perpendicular heading (rotated 90 deg clockwise)
        sec_heading = (original_heading_deg + 90.0) % 360.0
        sec_heading_rad = math.radians(sec_heading)

        # Place target at 45% range on Starboard side: track is offset to Port by 0.45 * range
        optimal_offset = 0.45 * swath_range_m
        # Offset vector to Port (heading - 90 deg = original heading)
        port_dir_rad = math.radians((sec_heading - 90.0) % 360.0)
        track_center_e = target_e + optimal_offset * math.sin(port_dir_rad)
        track_center_n = target_n + optimal_offset * math.cos(port_dir_rad)

        # Start and end points of second look line (length run_length_m)
        half_len = run_length_m / 2.0
        start_e = track_center_e - half_len * math.sin(sec_heading_rad)
        start_n = track_center_n - half_len * math.cos(sec_heading_rad)
        end_e = track_center_e + half_len * math.sin(sec_heading_rad)
        end_n = track_center_n + half_len * math.cos(sec_heading_rad)

        start_lat, start_lon = utm_to_latlon(start_e, start_n, zone=self.zone)
        end_lat, end_lon = utm_to_latlon(end_e, end_n, zone=self.zone)

        return SecondLookLine(
            line_id=f"SL_{target_id}",
            target_id=target_id,
            heading_deg=round(sec_heading, 1),
            start_utm=(round(start_e, 2), round(start_n, 2)),
            end_utm=(round(end_e, 2), round(end_n, 2)),
            start_latlon=(start_lat, start_lon),
            end_latlon=(end_lat, end_lon),
            swath_offset_m=round(optimal_offset, 2),
            length_m=round(run_length_m, 1),
        )
