"""
SagarNetra Preprocessing Package.
Physics-grounded sonar signal conditioning:
- quality: dropout, nav gap, altitude jump flagging and interpolation
- bottom_track: first return detection and Kalman altitude smoothing
- slant_range: water column removal and slant-to-ground conversion
- motion: along-track spatial resampling and yaw compensation
- gain: empirical gain normalisation and log dynamic range scaling
- despeckle: 7x7 Enhanced Lee filtering
- features: 3-channel feature stack (intensity + shadow + Sato ridge)
- tiler: 512x512 tile extraction with 25% overlap
- pipeline: end-to-end preprocessing runner
"""
from backend.sagarnetra.preprocess.quality import detect_ping_quality, clean_dropouts
from backend.sagarnetra.preprocess.bottom_track import track_bottom, AltitudeKalmanFilter
from backend.sagarnetra.preprocess.slant_range import (
    correct_slant_range_ping,
    correct_slant_range_waterfall,
    slant_to_ground_coord,
    ground_to_slant_coord,
)
from backend.sagarnetra.preprocess.motion import resample_along_track, compensate_yaw
from backend.sagarnetra.preprocess.gain import empirical_gain_normalisation, log_compress_and_scale
from backend.sagarnetra.preprocess.despeckle import enhanced_lee_filter, despeckle_waterfall
from backend.sagarnetra.preprocess.features import (
    compute_shadow_probability_map,
    sato_ridge_filter,
    generate_feature_stack,
)
from backend.sagarnetra.preprocess.tiler import extract_tiles, TiledWindow
from backend.sagarnetra.preprocess.pipeline import preprocess_survey_pings, PreprocessResult

__all__ = [
    "detect_ping_quality",
    "clean_dropouts",
    "track_bottom",
    "AltitudeKalmanFilter",
    "correct_slant_range_ping",
    "correct_slant_range_waterfall",
    "slant_to_ground_coord",
    "ground_to_slant_coord",
    "resample_along_track",
    "compensate_yaw",
    "empirical_gain_normalisation",
    "log_compress_and_scale",
    "enhanced_lee_filter",
    "despeckle_waterfall",
    "compute_shadow_probability_map",
    "sato_ridge_filter",
    "generate_feature_stack",
    "extract_tiles",
    "TiledWindow",
    "preprocess_survey_pings",
    "PreprocessResult",
]
