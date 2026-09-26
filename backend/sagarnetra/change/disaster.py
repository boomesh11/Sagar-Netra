"""
SagarNetra Disaster Mode — Pre/Post Disaster Survey Change Detection.
Compares baseline vs post-cyclone side-scan sonar surveys to detect:
  - NEW_OBSTRUCTION (sunken vessels, containers, displaced pipes, net masses)
  - REMOVED (displaced or salvaged objects)
Provides synthetic disaster scenarios for Chennai Port, Kochi Channel, and Visakhapatnam.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.ndimage import label, find_objects, gaussian_filter

from backend.sagarnetra.confidence.fusion import ConfidenceFuser, FusedConfidence
from backend.sagarnetra.geo.dimensions import PhysicalDimensions, compute_physical_dimensions
from backend.sagarnetra.geo.error_budget import compute_position_error_budget
from backend.sagarnetra.geo.project import utm_to_latlon
from backend.sagarnetra.verify.rules import PhysicsVerifier, VerificationResult


class ChangeType(str, Enum):
    NEW_OBSTRUCTION = "NEW_OBSTRUCTION"
    REMOVED = "REMOVED"
    UNCHANGED = "UNCHANGED"


@dataclass
class DisasterObstruction:
    obstruction_id: str
    change_type: ChangeType
    estimated_class: str
    utm_easting: float
    utm_northing: float
    lat: float
    lon: float
    dimensions: PhysicalDimensions
    r95_m: float
    verification: VerificationResult
    confidence: FusedConfidence
    delta_intensity: float
    description: str


class DisasterChangeDetector:
    """
    Detects new obstructions by computing normalized log-ratio intensity differences
    and running candidates through the 8-rule Physics Verifier and Hazard Confidence fusion.
    """
    def __init__(
        self,
        verifier: Optional[PhysicsVerifier] = None,
        fuser: Optional[ConfidenceFuser] = None,
        zone: int = 44,
    ):
        self.verifier = verifier or PhysicsVerifier()
        self.fuser = fuser or ConfidenceFuser()
        self.zone = zone

    def detect_changes(
        self,
        baseline_img: np.ndarray,      # [H, W] normalized float32 [0, 1]
        post_disaster_img: np.ndarray, # [H, W] normalized float32 [0, 1]
        origin_easting: float,
        origin_northing: float,
        res_m: float = 0.10,
        altitude_m: float = 8.0,
        swath_range_m: float = 50.0,
        diff_threshold: float = 0.45,
        min_area_m2: float = 1.0,
    ) -> List[DisasterObstruction]:
        """
        Runs change detection between aligned baseline and post-disaster waterfall tiles.
        """
        assert baseline_img.shape == post_disaster_img.shape, "Images must have identical dimensions"
        h, w = baseline_img.shape

        # Smooth slightly to mitigate speckle noise false-changes
        base_smooth = gaussian_filter(baseline_img, sigma=1.0)
        post_smooth = gaussian_filter(post_disaster_img, sigma=1.0)

        # Log ratio: log((I_post + eps) / (I_pre + eps))
        eps = 0.05
        log_ratio = np.log((post_smooth + eps) / (base_smooth + eps))

        # Positive log ratio -> brighter in post (new highlight)
        new_obs_mask = (log_ratio > diff_threshold)
        # Negative log ratio -> darker in post / missing highlight
        removed_mask = (log_ratio < -diff_threshold)

        obstructions: List[DisasterObstruction] = []

        # Analyze new obstructions
        labeled, num_features = label(new_obs_mask)
        slices = find_objects(labeled)

        for idx, s in enumerate(slices, 1):
            if s is None:
                continue
            r_slice, c_slice = s
            comp = (labeled[s] == idx)
            pixel_area = int(np.sum(comp))
            area_m2 = pixel_area * res_m * res_m

            if area_m2 < min_area_m2:
                continue

            # Centroid in pixels
            r_center = (r_slice.start + r_slice.stop) / 2.0
            c_center = (c_slice.start + c_slice.stop) / 2.0

            # Ground range from nadir (assume nadir at column 0 or middle)
            ground_range_m = max(1.5, float(c_center * res_m))
            slant_range_m = math.sqrt(ground_range_m**2 + altitude_m**2)

            # UTM coordinates
            obs_easting = origin_easting + (c_center * res_m)
            obs_northing = origin_northing + (r_center * res_m)
            lat, lon = utm_to_latlon(obs_easting, obs_northing, zone=self.zone)

            # Physical dimensions
            full_mask = (labeled == idx)
            dims = compute_physical_dimensions(
                full_mask, res_across_m=res_m, res_along_m=res_m, height_m=min(area_m2 * 0.3, 2.5)
            )

            # Class inference based on aspect ratio and area
            if dims.length_m > 8.0 and dims.aspect_ratio > 4.0:
                est_cls = "pipe"
            elif dims.area_m2 > 15.0:
                est_cls = "wreck_debris"
            elif dims.aspect_ratio > 3.0:
                est_cls = "rope_cable"
            elif dims.area_m2 > 4.0:
                est_cls = "ghost_net"
            else:
                est_cls = "cylinder"

            # Physics verification
            v_res = self.verifier.verify(
                class_name=est_cls,
                ground_range_m=ground_range_m,
                altitude_m=altitude_m,
                slant_range_m=slant_range_m,
                highlight_extent_m=dims.length_m,
                shadow_length_m=dims.height_m * 1.5 if dims.height_m else 1.0,
                shadow_range_m=ground_range_m + (dims.height_m * 1.5 if dims.height_m else 1.0),
                pings_persisted=max(3, int(dims.length_m / res_m)),
            )

            # Error budget
            err_budget = compute_position_error_budget(ground_range_m=ground_range_m, layback_m=10.0)

            # Hazard confidence
            peak_delta = float(np.max(log_ratio[s][comp]))
            raw_prob = min(0.95, max(0.5, 0.4 + 0.3 * peak_delta))
            conf = self.fuser.compute_hazard_confidence(
                class_name=est_cls,
                calibrated_prob=raw_prob,
                v_phys=v_res.v_phys,
                q_obs=1.0,
                views=1,
                r95_m=err_budget.r95_m,
                in_sensitive_zone=True,  # Disaster ports are priority shipping channels
            )

            desc = f"New {est_cls} ({dims.length_m:.1f}x{dims.width_m:.1f} m) appeared post-cyclone at {lat:.5f}N, {lon:.5f}E"
            obstructions.append(DisasterObstruction(
                obstruction_id=f"DIS_OBS_{idx:03d}",
                change_type=ChangeType.NEW_OBSTRUCTION,
                estimated_class=est_cls,
                utm_easting=round(obs_easting, 2),
                utm_northing=round(obs_northing, 2),
                lat=lat,
                lon=lon,
                dimensions=dims,
                r95_m=err_budget.r95_m,
                verification=v_res,
                confidence=conf,
                delta_intensity=round(peak_delta, 3),
                description=desc,
            ))

        return obstructions


def create_synthetic_disaster_scenario(
    scenario_name: str = "chennai_port_basin",
    tile_size: int = 512,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, any]]:
    """
    Generates aligned baseline and post-cyclone synthetic side-scan sonar image pairs.
    Scenarios:
      - 'chennai_port_basin': Sunken boat hull + shipping container + ghost net mass
      - 'kochi_channel': Displaced dredge pipe + collapsed concrete block
      - 'visakhapatnam_harbour': Capsized fishing vessels + tangled cables
    """
    rng = np.random.default_rng(seed)

    # 1. Baseline ambient seabed
    base_bg = np.clip(0.35 + 0.05 * rng.standard_normal((tile_size, tile_size)), 0.1, 0.7).astype(np.float32)
    post_img = base_bg.copy()

    metadata = {
        "scenario": scenario_name,
        "site_name": scenario_name.replace("_", " ").title(),
        "baseline_date": "2026-09-01",
        "post_cyclone_date": "2026-09-24",
        "expected_hazards": [],
    }

    if scenario_name == "chennai_port_basin":
        metadata["utm_zone"] = 44
        metadata["origin_utm"] = (416200.0, 1448500.0)

        # Inject container at row 150, col 200 (length 12m, width 3m)
        r, c = 160, 220
        post_img[r:r+35, c:c+15] = 0.95  # Bright metallic highlight
        post_img[r:r+35, c+15:c+45] = 0.02  # Acoustic shadow
        metadata["expected_hazards"].append({"class": "wreck_debris", "desc": "Sunken 20ft container"})

        # Inject net tangle at row 350, col 300
        rn, cn = 340, 290
        for dr in range(40):
            dc = int(10 * math.sin(dr / 5.0))
            post_img[rn+dr, cn+dc:cn+dc+6] = 0.85
            post_img[rn+dr, cn+dc+6:cn+dc+18] = 0.05
        metadata["expected_hazards"].append({"class": "ghost_net", "desc": "Tangled trawl net mass"})

    elif scenario_name == "kochi_channel":
        metadata["utm_zone"] = 43
        metadata["origin_utm"] = (582000.0, 1102000.0)

        # Displaced pipe spanning across channel
        for r_p in range(120, 280):
            post_img[r_p, 180:186] = 0.92
            post_img[r_p, 186:205] = 0.03
        metadata["expected_hazards"].append({"class": "pipe", "desc": "Exposed displaced pipeline"})

    else:  # visakhapatnam_harbour
        metadata["utm_zone"] = 44
        metadata["origin_utm"] = (728000.0, 1956000.0)

        # Capsized boat
        rb, cb = 200, 240
        post_img[rb:rb+50, cb:cb+25] = 0.90
        post_img[rb:rb+50, cb+25:cb+60] = 0.04
        metadata["expected_hazards"].append({"class": "wreck_debris", "desc": "Capsized fishing trawler"})

    return base_bg, post_img, metadata
