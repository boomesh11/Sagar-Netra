"""
Image-log reader — handles PNG/TIFF/JPG waterfall images + sidecar navigation CSV,
and GeoTIFF mosaics. Falls back to pixel-only mode if nav missing.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Generator, Optional

import numpy as np

from backend.sagarnetra.io.schema import Ping, PingFlag, Survey

logger = logging.getLogger(__name__)


def _load_nav_csv(csv_path: Path) -> list[dict]:
    """Load navigation CSV into list of row dicts."""
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def read_image_log(
    image_path: str | Path,
    nav_csv: Optional[str | Path] = None,
    survey_id: str = "image_log",
) -> tuple[Survey, list[Ping]]:
    """
    Read a waterfall image (PNG/TIFF/JPG) and optional navigation CSV.
    Each row of the image becomes one Ping.

    CSV columns expected (flexible): timestamp, lat, lon, heading, altitude, range_m
    Returns pixel-only pings if nav is absent (position=null with reason).
    """
    try:
        import cv2
    except ImportError:
        raise ImportError("opencv-python-headless required for image log reading.")

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Failed to read image: {image_path}")

    height, width = img.shape  # height=pings, width=samples

    # Load nav if present
    nav_rows: list[dict] = []
    if nav_csv is not None:
        nav_path = Path(nav_csv)
        if nav_path.exists():
            nav_rows = _load_nav_csv(nav_path)
        else:
            logger.warning("Nav CSV not found: %s — pixel-only mode.", nav_path)

    survey = Survey(
        survey_id=survey_id,
        sensor_model="image_log",
        files=[str(image_path)],
    )

    pings: list[Ping] = []
    for row_idx in range(height):
        samples = img[row_idx, :].tolist()
        flags: list[PingFlag] = []

        lat: Optional[float] = None
        lon: Optional[float] = None
        heading = 0.0
        altitude = 5.0
        range_m = 50.0
        timestamp = float(row_idx)

        if row_idx < len(nav_rows):
            nav = nav_rows[row_idx]
            try:
                lat = float(nav.get("lat", nav.get("latitude", "nan")))
                lon = float(nav.get("lon", nav.get("longitude", "nan")))
                if lat != lat or lon != lon:  # NaN check
                    lat = lon = None
                heading = float(nav.get("heading", 0.0))
                altitude = float(nav.get("altitude", 5.0))
                range_m = float(nav.get("range_m", 50.0))
                ts_raw = nav.get("timestamp", str(row_idx))
                timestamp = float(ts_raw)
            except (ValueError, KeyError):
                lat = lon = None
        else:
            flags.append(PingFlag.NAV_MISSING)

        if lat is None or lon is None:
            flags.append(PingFlag.NAV_MISSING)

        pings.append(Ping(
            ping_id=row_idx,
            timestamp_utc=timestamp,
            ship_lat=lat,
            ship_lon=lon,
            heading_deg=heading,
            altitude_m=altitude,
            range_m=range_m,
            stbd=samples,
            flags=list(set(flags)),
        ))

    return survey, pings
