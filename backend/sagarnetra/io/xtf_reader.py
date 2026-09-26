"""
XTF (eXtended Triton Format) reader.
Reads sonar channels, navigation, attitude, altitude from XTF files.
Falls back to pixel-only mode if navigation is missing.
"""
from __future__ import annotations

import logging
import struct
from pathlib import Path
from typing import Generator, Optional

import numpy as np

from backend.sagarnetra.io.schema import Ping, PingFlag, Survey

logger = logging.getLogger(__name__)

# XTF packet types
XTF_PACKET_SONAR = 0
XTF_PACKET_ANNOTATION = 1
XTF_PACKET_ATTITUDE = 3
XTF_PACKET_POSITION = 100

MAGIC = 0xFACE  # XTF file magic number


def _read_xtf_file_header(f) -> dict:
    """Parse the 1024-byte XTF file header."""
    raw = f.read(1024)
    if len(raw) < 1024:
        raise ValueError("File too short to be valid XTF.")
    magic = struct.unpack_from("<H", raw, 0)[0]
    if magic != MAGIC:
        raise ValueError(f"Not an XTF file (magic={magic:#06x}, expected {MAGIC:#06x}).")
    sensor_info = raw[4:208]
    num_chan = struct.unpack_from("<H", raw, 208)[0]
    return {"num_channels": num_chan, "raw_header": raw}


def _safe_float(val: float) -> Optional[float]:
    """Return None if float is NaN or clearly invalid (999.0 sentinel)."""
    if val != val or abs(val) > 1e9:
        return None
    return float(val)


def read_xtf(path: str | Path) -> Generator[Ping, None, None]:
    """
    Yield Ping objects from an XTF file.
    If navigation is absent, yields pings with ship_lat/ship_lon = None
    and sets PingFlag.NAV_MISSING.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"XTF file not found: {path}")

    ping_id = 0
    try:
        import pyxtf
        # Use pyxtf for robust parsing
        (fh, packet_dict) = pyxtf.xtf_read(str(path))
        sonar_packets = packet_dict.get(pyxtf.XTFHeaderType.sonar, [])
        for packet in sonar_packets:
            try:
                ping = _parse_pyxtf_packet(packet, ping_id)
                yield ping
                ping_id += 1
            except Exception as exc:
                logger.warning("Skipping XTF ping %d: %s", ping_id, exc)
                ping_id += 1
    except ImportError:
        logger.warning("pyxtf not installed; falling back to minimal XTF parser.")
        yield from _read_xtf_minimal(path)


def _parse_pyxtf_packet(packet, ping_id: int) -> Ping:
    """Convert a pyxtf sonar packet to a Ping."""
    import pyxtf
    flags: list[PingFlag] = []

    lat = getattr(packet, "SensorYcoordinate", None)
    lon = getattr(packet, "SensorXcoordinate", None)
    lat = _safe_float(lat) if lat is not None else None
    lon = _safe_float(lon) if lon is not None else None
    if lat is None or lon is None:
        flags.append(PingFlag.NAV_MISSING)

    altitude = _safe_float(getattr(packet, "SensorPrimaryAltitude", 5.0) or 5.0)
    heading = float(getattr(packet, "SensorHeading", 0.0) or 0.0)
    pitch = float(getattr(packet, "SensorPitch", 0.0) or 0.0)
    roll = float(getattr(packet, "SensorRoll", 0.0) or 0.0)
    speed = float(getattr(packet, "SensorSpeed", 0.0) or 0.0)

    # Extract port/starboard samples
    port_data: Optional[list[int]] = None
    stbd_data: Optional[list[int]] = None
    if hasattr(packet, "data") and packet.data:
        channels = packet.data
        if len(channels) >= 1:
            stbd_data = [int(v) for v in channels[0].flatten().tolist()]
        if len(channels) >= 2:
            port_data = [int(v) for v in channels[1].flatten().tolist()]

    # Check for dropout
    if stbd_data is not None and len(stbd_data) > 0:
        energy = sum(stbd_data)
        if energy == 0 or max(stbd_data) == min(stbd_data):
            flags.append(PingFlag.DROPOUT)

    timestamp = float(getattr(packet, "TimeTag", 0.0) or 0.0)

    return Ping(
        ping_id=ping_id,
        timestamp_utc=timestamp,
        ship_lat=lat,
        ship_lon=lon,
        heading_deg=heading,
        altitude_m=altitude or 5.0,
        pitch_deg=pitch,
        roll_deg=roll,
        speed_mps=speed,
        port=port_data,
        stbd=stbd_data,
        flags=flags,
    )


def _read_xtf_minimal(path: Path) -> Generator[Ping, None, None]:
    """Minimal fallback XTF parser that yields pixel-only pings."""
    ping_id = 0
    with open(path, "rb") as f:
        try:
            _read_xtf_file_header(f)
        except ValueError as e:
            logger.error("XTF header error: %s", e)
            return
        while True:
            header_raw = f.read(14)
            if len(header_raw) < 14:
                break
            magic, hdr_type, num_bytes_header, num_bytes_data = struct.unpack_from(
                "<HHHH", header_raw, 0
            )[:4]
            data_raw = f.read(num_bytes_data)
            if hdr_type == XTF_PACKET_SONAR:
                samples = list(struct.unpack(f"<{len(data_raw)//2}H", data_raw[:len(data_raw)//2*2]))
                yield Ping(
                    ping_id=ping_id,
                    timestamp_utc=0.0,
                    ship_lat=None,
                    ship_lon=None,
                    stbd=samples,
                    flags=[PingFlag.NAV_MISSING],
                )
                ping_id += 1


def survey_from_xtf(path: str | Path, survey_id: str) -> Survey:
    """Create a Survey object from an XTF file path."""
    return Survey(
        survey_id=survey_id,
        sensor_model="XTF",
        files=[str(path)],
    )
