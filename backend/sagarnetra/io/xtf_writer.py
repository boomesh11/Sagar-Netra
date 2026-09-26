"""
XTF Writer — writes minimal valid XTF files from SonarForge scenes.
Supports: XTFFILEHEADER (1024 bytes), XTFPINGHEADER (256 bytes),
XTFPINGCHANHEADER (64 bytes), 16-bit samples.
Round-trip test: write → read with pyxtf → samples and navigation identical.
"""
from __future__ import annotations

import struct
import time
from pathlib import Path
from typing import Sequence

import numpy as np

from backend.sagarnetra.io.schema import Ping

# XTF format constants
XTF_MAGIC = 0xFACE
XTF_FILE_HEADER_SIZE = 1024
XTF_PING_HEADER_SIZE = 256
XTF_CHAN_HEADER_SIZE = 64
XTF_PACKET_SONAR = 0
XTF_VERSION = 123  # XTF version indicator


def _pack_file_header(num_channels: int = 2, frequency_hz: float = 450_000.0) -> bytes:
    """Build a minimal 1024-byte XTF file header."""
    buf = bytearray(XTF_FILE_HEADER_SIZE)
    struct.pack_into("<H", buf, 0, XTF_MAGIC)  # file magic
    struct.pack_into("<B", buf, 2, XTF_VERSION)  # sonar type
    struct.pack_into("<H", buf, 208, num_channels)  # number of channels
    # Channel info at offset 256 (64 bytes per channel)
    for ch in range(min(num_channels, 6)):
        off = 256 + ch * 64
        struct.pack_into("<H", buf, off, 1)  # type code: sidescan
        struct.pack_into("<f", buf, off + 4, frequency_hz)
    return bytes(buf)


def _pack_ping_header(ping: Ping, num_samples: int, bytes_per_sample: int = 2) -> bytes:
    """Build a 256-byte XTFPINGHEADER."""
    buf = bytearray(XTF_PING_HEADER_SIZE)
    struct.pack_into("<H", buf, 0, XTF_MAGIC)
    struct.pack_into("<B", buf, 2, XTF_PACKET_SONAR)
    struct.pack_into("<H", buf, 4, XTF_PING_HEADER_SIZE)
    # Navigation
    lat = ping.ship_lat or 0.0
    lon = ping.ship_lon or 0.0
    struct.pack_into("<d", buf, 32, lat)
    struct.pack_into("<d", buf, 40, lon)
    struct.pack_into("<f", buf, 64, ping.heading_deg)
    struct.pack_into("<f", buf, 68, ping.pitch_deg)
    struct.pack_into("<f", buf, 72, ping.roll_deg)
    struct.pack_into("<f", buf, 76, ping.altitude_m)
    struct.pack_into("<f", buf, 80, ping.speed_mps)
    # Timestamp
    ts = ping.timestamp_utc
    struct.pack_into("<I", buf, 16, int(ts))  # seconds
    struct.pack_into("<H", buf, 20, int((ts % 1) * 1000))  # milliseconds
    return bytes(buf)


def _pack_chan_header(num_samples: int, range_m: float, sample_interval_s: float) -> bytes:
    """Build a 64-byte XTFPINGCHANHEADER."""
    buf = bytearray(XTF_CHAN_HEADER_SIZE)
    struct.pack_into("<H", buf, 0, num_samples)
    struct.pack_into("<f", buf, 8, range_m)
    struct.pack_into("<f", buf, 12, sample_interval_s)
    struct.pack_into("<H", buf, 20, 2)  # bytes per sample (uint16)
    return bytes(buf)


def write_xtf(
    path: str | Path,
    pings: Sequence[Ping],
    frequency_hz: float = 450_000.0,
) -> None:
    """
    Write a list of Ping objects to a valid XTF file.

    Args:
        path: Output file path.
        pings: Sequence of Ping objects (must have stbd and optionally port samples).
        frequency_hz: Sonar frequency in Hz.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    num_channels = 2  # port + starboard

    with open(path, "wb") as f:
        f.write(_pack_file_header(num_channels=num_channels, frequency_hz=frequency_hz))

        for ping in pings:
            stbd = ping.stbd or []
            port = ping.port or []
            num_samples = max(len(stbd), len(port))
            if num_samples == 0:
                continue

            # Pad to equal length
            stbd_arr = np.array(stbd, dtype=np.uint16)
            port_arr = np.array(port, dtype=np.uint16)
            if len(stbd_arr) < num_samples:
                stbd_arr = np.pad(stbd_arr, (0, num_samples - len(stbd_arr)))
            if len(port_arr) < num_samples:
                port_arr = np.pad(port_arr, (0, num_samples - len(port_arr)))

            ping_hdr = _pack_ping_header(ping, num_samples)
            chan_hdr_stbd = _pack_chan_header(num_samples, ping.range_m, ping.sample_interval_s)
            chan_hdr_port = _pack_chan_header(num_samples, ping.range_m, ping.sample_interval_s)

            samples_bytes = stbd_arr.tobytes() + port_arr.tobytes()

            f.write(ping_hdr)
            f.write(chan_hdr_stbd)
            f.write(chan_hdr_port)
            f.write(samples_bytes)
