"""
SagarNetra Detection Package.
Physics-grounded candidate generation and detection heads:
- cfar: 2D OS-CFAR detector with highlight-shadow pairing
- net_signature: Net Signature Head (LoG floats, MST regularity, skeleton length, Gabor mesh)
- fuse_candidates: candidate union and Non-Maximum Suppression (NMS)
"""
from backend.sagarnetra.detect.cfar import (
    CFARCandidate,
    os_cfar_2d,
    pair_highlights_and_shadows,
)
from backend.sagarnetra.detect.net_signature import (
    NetSignatureResult,
    detect_float_blobs,
    gabor_mesh_energy,
    evaluate_net_signature,
)
from backend.sagarnetra.detect.fuse_candidates import (
    FusedCandidate,
    compute_iou,
    nms_candidates,
    fuse_cfar_and_net_signature,
)

__all__ = [
    "CFARCandidate",
    "os_cfar_2d",
    "pair_highlights_and_shadows",
    "NetSignatureResult",
    "detect_float_blobs",
    "gabor_mesh_energy",
    "evaluate_net_signature",
    "FusedCandidate",
    "compute_iou",
    "nms_candidates",
    "fuse_cfar_and_net_signature",
]
