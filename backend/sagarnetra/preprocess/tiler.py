"""
SagarNetra Preprocessing — Tiler.
Splits ground-corrected waterfall feature stacks into 512x512 tiles
with 25% spatial overlap (stride 384 pixels) per sonar channel.
Carries spatial metadata and quality masks for downstream inference.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generator, List, Optional, Tuple
import numpy as np

from backend.sagarnetra.io.schema import Tile


@dataclass
class TiledWindow:
    tile_id: str
    survey_id: str
    side: str                          # "port" or "stbd"
    feature_stack: np.ndarray          # Shape: [tile_size, tile_size, 3] float32
    raw_intensity: np.ndarray          # Shape: [tile_size, tile_size] float32
    quality_mask: np.ndarray           # Shape: [tile_size, tile_size] bool (True = valid)
    row_start: int                     # Along-track row start index in waterfall
    row_end: int                       # Along-track row end index in waterfall
    col_start: int                     # Across-track column start index
    col_end: int                       # Across-track column end index
    ping_start: int                    # Survey ping index start
    ping_end: int                      # Survey ping index end
    ground_res_m: float                # Spatial resolution in meters
    ground_ranges_m: np.ndarray        # Horizontal distances for columns [tile_size]
    along_track_m: np.ndarray          # Along-track distances for rows [tile_size]

    def to_schema(self) -> Tile:
        return Tile(
            tile_id=self.tile_id,
            survey_id=self.survey_id,
            side=self.side,
            ping_start=self.ping_start,
            ping_end=self.ping_end,
            ground_res_m=self.ground_res_m,
            quality_mask=self.quality_mask.tolist() if self.quality_mask.size <= 256*256 else None,
        )


def extract_tiles(
    feature_stack: np.ndarray,
    raw_intensity: np.ndarray,
    quality_mask: np.ndarray,
    ground_ranges_m: np.ndarray,
    along_track_m: np.ndarray,
    ping_indices: np.ndarray,
    survey_id: str,
    side: str,
    tile_size: int = 512,
    overlap_fraction: float = 0.25,
    ground_res_m: float = 0.10,
) -> List[TiledWindow]:
    """
    Extracts fixed-dimension overlapping tiles from the processed waterfall.
    
    Args:
        feature_stack: [H, W, 3] float32 array
        raw_intensity: [H, W] float32 array
        quality_mask: [H, W] bool array (True = valid)
        ground_ranges_m: [W] across-track coordinates in meters
        along_track_m: [H] along-track coordinates in meters
        ping_indices: [H] original ping indices
        survey_id: identifier of the survey
        side: "port" or "stbd"
        tile_size: width and height of output tiles (default 512)
        overlap_fraction: overlap between adjacent tiles (default 0.25 = stride 384)
        ground_res_m: pixel spatial resolution
        
    Returns:
        List of TiledWindow objects ready for detector inference.
    """
    h, w, c = feature_stack.shape
    stride = int(round(tile_size * (1.0 - overlap_fraction)))
    tiles: List[TiledWindow] = []

    # If image is smaller than tile_size, pad to tile_size
    pad_h = max(0, tile_size - h)
    pad_w = max(0, tile_size - w)

    if pad_h > 0 or pad_w > 0:
        feature_padded = np.pad(feature_stack, ((0, pad_h), (0, pad_w), (0, 0)), mode="constant", constant_values=0)
        raw_padded = np.pad(raw_intensity, ((0, pad_h), (0, pad_w)), mode="constant", constant_values=0)
        quality_padded = np.pad(quality_mask, ((0, pad_h), (0, pad_w)), mode="constant", constant_values=False)

        # Extended coordinate arrays
        ext_ranges = np.arange(w + pad_w, dtype=np.float32) * ground_res_m
        ext_along = np.arange(h + pad_h, dtype=np.float32) * ground_res_m
        ext_pings = np.pad(ping_indices, (0, pad_h), mode="edge")
    else:
        feature_padded = feature_stack
        raw_padded = raw_intensity
        quality_padded = quality_mask
        ext_ranges = ground_ranges_m
        ext_along = along_track_m
        ext_pings = ping_indices

    cur_h, cur_w, _ = feature_padded.shape

    # Generate step ranges
    row_starts = list(range(0, cur_h - tile_size + 1, stride))
    if not row_starts or row_starts[-1] + tile_size < cur_h:
        row_starts.append(max(0, cur_h - tile_size))

    col_starts = list(range(0, cur_w - tile_size + 1, stride))
    if not col_starts or col_starts[-1] + tile_size < cur_w:
        col_starts.append(max(0, cur_w - tile_size))

    # Remove duplicates
    row_starts = sorted(list(set(row_starts)))
    col_starts = sorted(list(set(col_starts)))

    for r_start in row_starts:
        r_end = r_start + tile_size
        for c_start in col_starts:
            c_end = c_start + tile_size

            tile_feat = feature_padded[r_start:r_end, c_start:c_end]
            tile_raw = raw_padded[r_start:r_end, c_start:c_end]
            tile_qual = quality_padded[r_start:r_end, c_start:c_end]

            p_start_val = int(ext_pings[min(r_start, len(ext_pings) - 1)])
            p_end_val = int(ext_pings[min(r_end - 1, len(ext_pings) - 1)])

            tile_id = f"{survey_id}_{side}_r{r_start}_c{c_start}"

            window = TiledWindow(
                tile_id=tile_id,
                survey_id=survey_id,
                side=side,
                feature_stack=tile_feat,
                raw_intensity=tile_raw,
                quality_mask=tile_qual,
                row_start=r_start,
                row_end=r_end,
                col_start=c_start,
                col_end=c_end,
                ping_start=p_start_val,
                ping_end=p_end_val,
                ground_res_m=ground_res_m,
                ground_ranges_m=ext_ranges[c_start:c_end],
                along_track_m=ext_along[r_start:r_end],
            )
            tiles.append(window)

    return tiles
