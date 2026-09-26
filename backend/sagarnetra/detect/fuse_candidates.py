"""
SagarNetra Detection — Candidate Fusion and NMS.
Merges candidate detections from Stage A (CFAR), Net Signature Head (S_net > 0.6),
and Stage B (YOLO/ONNX), applying 2D bounding-box Non-Maximum Suppression (NMS).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import numpy as np

from backend.sagarnetra.detect.cfar import CFARCandidate
from backend.sagarnetra.detect.net_signature import NetSignatureResult


@dataclass
class FusedCandidate:
    candidate_id: str
    side: str                          # "port" or "stbd"
    row_start: int
    row_end: int
    col_start: int
    col_end: int
    score: float                       # Confidence / saliency score in [0.0, 1.0]
    source_stage: str                  # "cfar" | "net_sig" | "ml" | "fused"
    has_shadow: bool
    shadow_length_m: float
    ground_range_m: float
    s_net: float
    evidence: str


def compute_iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    """
    Computes Intersection-over-Union (IoU) between two bounding boxes:
    (r_min, r_max, c_min, c_max)
    """
    r_a1, r_a2, c_a1, c_a2 = box_a
    r_b1, r_b2, c_b1, c_b2 = box_b

    # Intersection
    r_int1 = max(r_a1, r_b1)
    r_int2 = min(r_a2, r_b2)
    c_int1 = max(c_a1, c_b1)
    c_int2 = min(c_a2, c_b2)

    if r_int2 <= r_int1 or c_int2 <= c_int1:
        return 0.0

    inter_area = (r_int2 - r_int1) * (c_int2 - c_int1)
    area_a = (r_a2 - r_a1) * (c_a2 - c_a1)
    area_b = (r_b2 - r_b1) * (c_b2 - c_b1)
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0
    return float(inter_area / union_area)


def nms_candidates(
    candidates: List[FusedCandidate],
    iou_threshold: float = 0.5,
) -> List[FusedCandidate]:
    """
    Performs Non-Maximum Suppression (NMS) on candidates sorted by score descending.
    """
    if not candidates:
        return []

    # Sort descending by score
    sorted_cands = sorted(candidates, key=lambda c: c.score, reverse=True)
    kept: List[FusedCandidate] = []

    for cand in sorted_cands:
        box_cand = (cand.row_start, cand.row_end, cand.col_start, cand.col_end)
        should_keep = True

        for existing in kept:
            if existing.side != cand.side:
                continue
            box_existing = (existing.row_start, existing.row_end, existing.col_start, existing.col_end)
            if compute_iou(box_cand, box_existing) >= iou_threshold:
                should_keep = False
                break

        if should_keep:
            kept.append(cand)

    return kept


def fuse_cfar_and_net_signature(
    cfar_cands: List[CFARCandidate],
    image: np.ndarray,
    ground_res_m: float = 0.10,
    net_sig_threshold: float = 0.50,
) -> List[FusedCandidate]:
    """
    Combines CFAR highlight-shadow candidates and Net Signature evidence.
    Evaluates Net Signature in candidate regions and boosts net confidence.
    """
    from backend.sagarnetra.detect.net_signature import evaluate_net_signature

    fused_list: List[FusedCandidate] = []
    # Sort candidates by SNR and highlight area to prioritize strong detections
    sorted_cands = sorted(cfar_cands, key=lambda c: (c.has_shadow, c.snr_db), reverse=True)[:30]

    for c in sorted_cands:
        # Extract candidate crop with safe padding
        pad = 5
        r1 = max(0, c.row_start - pad)
        r2 = min(image.shape[0], c.row_end + pad)
        c1 = max(0, c.col_start - pad)
        c2 = min(image.shape[1], c.col_end + pad)

        crop = image[r1:r2, c1:c2]
        if crop.size > 20:
            net_res = evaluate_net_signature(crop, ground_res_m=ground_res_m)
            s_net = net_res.s_net
            ev = f"CFAR highlight (SNR {c.snr_db:.1f} dB)"
            if c.has_shadow:
                ev += f", shadow length {c.shadow_length_m:.1f}m"
            if net_res.evidence and net_res.evidence != "No distinct net features":
                ev += f"; {net_res.evidence}"
        else:
            s_net = 0.0
            ev = f"CFAR highlight (SNR {c.snr_db:.1f} dB)"

        # Score calculation: base CFAR SNR + shadow presence + Net signature
        base_score = min(c.snr_db / 20.0, 0.5)
        shadow_boost = 0.3 if c.has_shadow else 0.0
        net_boost = 0.2 * s_net
        total_score = min(base_score + shadow_boost + net_boost, 1.0)

        fused = FusedCandidate(
            candidate_id=c.candidate_id,
            side=c.side,
            row_start=c.row_start,
            row_end=c.row_end,
            col_start=c.col_start,
            col_end=c.col_end,
            score=total_score,
            source_stage="fused" if s_net > 0.3 else "cfar",
            has_shadow=c.has_shadow,
            shadow_length_m=c.shadow_length_m,
            ground_range_m=c.ground_range_m,
            s_net=s_net,
            evidence=ev,
        )
        fused_list.append(fused)

    return nms_candidates(fused_list, iou_threshold=0.5)
