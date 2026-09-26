"""
SagarNetra Preprocessing Pipeline.
Coordinates end-to-end preprocessing from raw survey pings to 512x512 feature tiles:
1. Quality checks & dropout cleanup
2. Bottom-track & Kalman altitude estimation
3. Slant-range to ground-range conversion
4. Along-track motion & yaw compensation
5. Empirical gain normalisation & log-scaling
6. 7x7 Enhanced Lee despeckling
7. 3-channel feature stack (intensity + shadow + Sato ridge)
8. 512x512 overlapping tiling
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np

from backend.sagarnetra.io.schema import Ping, PingFlags, Tile
from backend.sagarnetra.preprocess.quality import detect_ping_quality, clean_dropouts
from backend.sagarnetra.preprocess.bottom_track import track_bottom
from backend.sagarnetra.preprocess.slant_range import correct_slant_range_waterfall
from backend.sagarnetra.preprocess.motion import resample_along_track, compensate_yaw
from backend.sagarnetra.preprocess.gain import empirical_gain_normalisation, log_compress_and_scale
from backend.sagarnetra.preprocess.despeckle import despeckle_waterfall
from backend.sagarnetra.preprocess.features import generate_feature_stack
from backend.sagarnetra.preprocess.tiler import extract_tiles, TiledWindow


@dataclass
class PreprocessedChannel:
    side: str
    feature_stack: np.ndarray        # [H, W, 3] float32
    raw_intensity: np.ndarray        # [H, W] float32
    quality_mask: np.ndarray         # [H, W] bool (True = valid)
    ground_ranges_m: np.ndarray      # [W] horizontal distance
    along_track_m: np.ndarray        # [H] along track distance
    ping_indices: np.ndarray         # [H] mapped ping indices
    tiles: List[TiledWindow]         # 512x512 tiles


@dataclass
class PreprocessResult:
    survey_id: str
    flags: List[PingFlags]
    port: PreprocessedChannel
    stbd: PreprocessedChannel
    altitudes_m: np.ndarray          # [num_pings] tracked altitude
    altitude_disagreements: int      # Count of pings where tracked != header


def preprocess_survey_pings(
    pings: List[Ping],
    survey_id: str = "survey_01",
    ground_res_m: float = 0.10,
    along_res_m: float = 0.10,
    max_ground_range_m: float = 50.0,
    tile_size: int = 512,
    tile_overlap: float = 0.25,
) -> PreprocessResult:
    """
    Executes complete preprocessing on a sequence of sonar pings.
    """
    n_pings = len(pings)
    if n_pings == 0:
        raise ValueError("Cannot preprocess empty ping list")

    # Extract raw waterfalls and metadata
    n_port = len(pings[0].port)
    n_stbd = len(pings[0].stbd)
    port_raw = np.zeros((n_pings, n_port), dtype=np.uint16)
    stbd_raw = np.zeros((n_pings, n_stbd), dtype=np.uint16)
    hdr_alts = np.zeros(n_pings, dtype=np.float32)
    timestamps = np.zeros(n_pings, dtype=np.float64)
    speeds = np.zeros(n_pings, dtype=np.float32)
    yaw_angles = np.zeros(n_pings, dtype=np.float32)

    sample_spacing_m = (pings[0].sound_speed_mps * pings[0].sample_interval_s) / 2.0

    for i, p in enumerate(pings):
        port_raw[i] = np.asarray(p.port, dtype=np.uint16)
        stbd_raw[i] = np.asarray(p.stbd, dtype=np.uint16)
        hdr_alts[i] = float(p.altitude_m)
        timestamps[i] = float(p.timestamp_utc)
        speeds[i] = float(p.speed_mps) if p.speed_mps > 0 else 2.0
        yaw_angles[i] = float(p.yaw_deg)

    # 1. Quality flagging & dropout cleanup
    flags = detect_ping_quality(pings)
    port_clean, stbd_clean, no_data_pings = clean_dropouts(port_raw, stbd_raw, flags)

    # 2. Bottom track & altitude estimation
    bt_res = track_bottom(
        port_waterfall=port_clean,
        stbd_waterfall=stbd_clean,
        header_altitudes=hdr_alts,
        sample_spacing_m=sample_spacing_m,
    )
    altitudes = bt_res.estimated_altitudes_m

    # Process channels: Port and Starboard
    channels: dict[str, PreprocessedChannel] = {}

    for side, waterfall_raw in [("port", port_clean), ("stbd", stbd_clean)]:
        # 3. Slant-range correction
        slant_res = correct_slant_range_waterfall(
            waterfall=waterfall_raw,
            altitudes_m=altitudes,
            sample_spacing_m=sample_spacing_m,
            ground_res_m=ground_res_m,
            max_ground_range_m=max_ground_range_m,
        )

        # 4. Motion & along-track spatial resampling
        motion_res = resample_along_track(
            ground_image=slant_res.ground_image,
            timestamps_s=timestamps,
            speeds_mps=speeds,
            along_res_m=along_res_m,
        )

        # Yaw compensation
        interp_yaw = np.interp(
            motion_res.along_track_dist_m,
            np.linspace(0, motion_res.along_track_dist_m[-1] if len(motion_res.along_track_dist_m) > 0 else 1.0, n_pings),
            yaw_angles,
        )
        rectified = compensate_yaw(
            motion_res.resampled_image,
            interp_yaw,
            ground_res_m=ground_res_m,
            along_res_m=along_res_m,
        )

        # 5. Empirical Gain Normalisation & dynamic range log-scaling
        gain_norm = empirical_gain_normalisation(rectified)
        scaled_intensity = log_compress_and_scale(gain_norm)

        # 6. Enhanced Lee despeckling
        despeckled, raw_layer = despeckle_waterfall(scaled_intensity, window_size=7)

        # 7. Acoustic feature stack (ch0: intensity, ch1: shadow, ch2: Sato ridge)
        feat_stack = generate_feature_stack(despeckled)

        # Build quality mask for the resampled waterfall
        # Interpolate ping dropout flags to along-track bins
        interp_nodata = np.interp(
            motion_res.original_ping_indices,
            np.arange(n_pings),
            no_data_pings.astype(np.float32),
        ) > 0.5
        quality_mask = np.ones(rectified.shape, dtype=bool)
        quality_mask[interp_nodata, :] = False

        # 8. Tiling
        tiles = extract_tiles(
            feature_stack=feat_stack,
            raw_intensity=raw_layer,
            quality_mask=quality_mask,
            ground_ranges_m=slant_res.ground_ranges_m,
            along_track_m=motion_res.along_track_dist_m,
            ping_indices=motion_res.original_ping_indices,
            survey_id=survey_id,
            side=side,
            tile_size=tile_size,
            overlap_fraction=tile_overlap,
            ground_res_m=ground_res_m,
        )

        channels[side] = PreprocessedChannel(
            side=side,
            feature_stack=feat_stack,
            raw_intensity=raw_layer,
            quality_mask=quality_mask,
            ground_ranges_m=slant_res.ground_ranges_m,
            along_track_m=motion_res.along_track_dist_m,
            ping_indices=motion_res.original_ping_indices,
            tiles=tiles,
        )

    return PreprocessResult(
        survey_id=survey_id,
        flags=flags,
        port=channels["port"],
        stbd=channels["stbd"],
        altitudes_m=altitudes,
        altitude_disagreements=int(np.sum(bt_res.disagreement_flags)),
    )
