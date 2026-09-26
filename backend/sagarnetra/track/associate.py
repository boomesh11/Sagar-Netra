"""
SagarNetra Tracking — Multi-View Detection Association across Survey Lines.
Associates detections observed from different survey passes using overlapping
error ellipses (r95) and updates position, confidence, and view counts.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

from backend.sagarnetra.confidence.fusion import ConfidenceFuser, FusedConfidence
from backend.sagarnetra.geo.error_budget import PositionErrorBudget
from backend.sagarnetra.geo.project import utm_to_latlon


@dataclass
class GeoreferencedDetection:
    detection_id: str
    class_name: str
    utm_easting: float
    utm_northing: float
    zone: int
    lat: float
    lon: float
    r95_m: float
    calibrated_prob: float
    v_phys: float
    s_net: float
    q_obs: float
    survey_line_id: str
    timestamp: float
    length_m: float = 1.0
    width_m: float = 0.5
    height_m: Optional[float] = None
    views: int = 1
    fused_confidence: Optional[FusedConfidence] = None


@dataclass
class AssociatedTarget:
    target_id: str
    class_name: str
    utm_easting: float
    utm_northing: float
    zone: int
    lat: float
    lon: float
    r95_m: float
    views: int
    contributing_detections: List[str] = field(default_factory=list)
    fused_confidence: Optional[FusedConfidence] = None
    length_m: float = 1.0
    width_m: float = 0.5
    height_m: Optional[float] = None


class MultiViewAssociator:
    """
    Associates sonar detections across multiple passes/survey lines.
    """
    def __init__(self, fuser: Optional[ConfidenceFuser] = None):
        self.fuser = fuser or ConfidenceFuser()

    def associate_detections(
        self,
        detections: List[GeoreferencedDetection],
    ) -> List[AssociatedTarget]:
        """
        Groups detections by overlapping uncertainty radii and spatial proximity.
        """
        if not detections:
            return []

        clusters: List[List[GeoreferencedDetection]] = []
        assigned = set()

        for i, det_a in enumerate(detections):
            if i in assigned:
                continue

            current_cluster = [det_a]
            assigned.add(i)

            for j in range(i + 1, len(detections)):
                if j in assigned:
                    continue
                det_b = detections[j]

                # Don't merge detections from the same ping / line if too close to avoid collapsing distinct objects
                dist = math.sqrt(
                    (det_a.utm_easting - det_b.utm_easting)**2 +
                    (det_a.utm_northing - det_b.utm_northing)**2
                )
                max_allowed_dist = det_a.r95_m + det_b.r95_m

                # Class compatibility: must be identical class or closely related hazard
                class_match = (det_a.class_name == det_b.class_name) or (
                    det_a.class_name in ["ghost_net", "rope_cable"] and det_b.class_name in ["ghost_net", "rope_cable"]
                )

                if dist <= max_allowed_dist and class_match:
                    current_cluster.append(det_b)
                    assigned.add(j)

            clusters.append(current_cluster)

        # Merge clusters into unified AssociatedTargets
        associated_targets = []
        for cluster_idx, cluster in enumerate(clusters, 1):
            target = self._merge_cluster(cluster_idx, cluster)
            associated_targets.append(target)

        return associated_targets

    def _merge_cluster(
        self,
        cluster_idx: int,
        cluster: List[GeoreferencedDetection],
    ) -> AssociatedTarget:
        n_views = len(cluster)
        zone = cluster[0].zone
        primary_class = cluster[0].class_name

        if n_views == 1:
            det = cluster[0]
            # Ensure fused confidence with views=1
            fused = det.fused_confidence or self.fuser.compute_hazard_confidence(
                class_name=det.class_name,
                calibrated_prob=det.calibrated_prob,
                v_phys=det.v_phys,
                q_obs=det.q_obs,
                s_net=det.s_net,
                views=1,
                r95_m=det.r95_m,
            )
            return AssociatedTarget(
                target_id=f"TGT_{zone}_{cluster_idx:04d}",
                class_name=det.class_name,
                utm_easting=det.utm_easting,
                utm_northing=det.utm_northing,
                zone=zone,
                lat=det.lat,
                lon=det.lon,
                r95_m=det.r95_m,
                views=1,
                contributing_detections=[det.detection_id],
                fused_confidence=fused,
                length_m=det.length_m,
                width_m=det.width_m,
                height_m=det.height_m,
            )

        # Multi-view weighted fusion
        weights = []
        for det in cluster:
            sigma = max(det.r95_m / 2.45, 0.5)
            w = 1.0 / (sigma**2)
            weights.append(w)

        total_weight = sum(weights)
        merged_easting = sum(det.utm_easting * w for det, w in zip(cluster, weights)) / total_weight
        merged_northing = sum(det.utm_northing * w for det, w in zip(cluster, weights)) / total_weight

        # Refined combined uncertainty
        sigma_merged = 1.0 / math.sqrt(total_weight)
        r95_merged = round(2.45 * sigma_merged, 2)

        merged_lat, merged_lon = utm_to_latlon(merged_easting, merged_northing, zone=zone)

        # Average physical dimensions
        avg_len = float(np.mean([d.length_m for d in cluster]))
        avg_wid = float(np.mean([d.width_m for d in cluster]))
        valid_heights = [d.height_m for d in cluster if d.height_m is not None]
        avg_h = float(np.mean(valid_heights)) if valid_heights else None

        # Re-compute Hazard Confidence with multi-view bonus
        max_prob = max(d.calibrated_prob for d in cluster)
        avg_v_phys = float(np.mean([d.v_phys for d in cluster]))
        avg_q_obs = float(np.mean([d.q_obs for d in cluster]))
        max_s_net = max(d.s_net for d in cluster)

        merged_confidence = self.fuser.compute_hazard_confidence(
            class_name=primary_class,
            calibrated_prob=max_prob,
            v_phys=avg_v_phys,
            q_obs=avg_q_obs,
            s_net=max_s_net,
            views=n_views,
            r95_m=r95_merged,
        )

        return AssociatedTarget(
            target_id=f"TGT_{zone}_{cluster_idx:04d}",
            class_name=primary_class,
            utm_easting=round(merged_easting, 2),
            utm_northing=round(merged_northing, 2),
            zone=zone,
            lat=merged_lat,
            lon=merged_lon,
            r95_m=r95_merged,
            views=n_views,
            contributing_detections=[d.detection_id for d in cluster],
            fused_confidence=merged_confidence,
            length_m=round(avg_len, 2),
            width_m=round(avg_wid, 2),
            height_m=round(avg_h, 2) if avg_h is not None else None,
        )
