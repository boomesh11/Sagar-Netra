"""
SonarForge navigation — generates lawnmower survey lines around Indian demo sites.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Generator

import numpy as np


DEMO_SITES = {
    "CHENNAI_PORT":      (13.10, 80.30),
    "KOCHI":             (9.97,  76.24),
    "VISAKHAPATNAM":     (17.69, 83.29),
    "GULF_OF_MANNAR":    (9.10,  79.20),
    "JNPT_MUMBAI":       (18.95, 72.95),
    "PARADIP":           (20.26, 86.68),
}

WGS84_A = 6_378_137.0  # semi-major axis (m)


def lat_lon_to_utm_approx(lat: float, lon: float) -> tuple[float, float]:
    """Approximate WGS84 → local East/North metres from origin."""
    lat_rad = math.radians(lat)
    scale = math.cos(lat_rad)
    E = lon * math.pi / 180.0 * WGS84_A * scale
    N = lat * math.pi / 180.0 * WGS84_A
    return E, N


def utm_to_lat_lon_approx(E0: float, N0: float, E: float, N: float, lat0: float, lon0: float) -> tuple[float, float]:
    """Convert local offset metres back to lat/lon."""
    lat_rad = math.radians(lat0)
    scale = math.cos(lat_rad)
    dlat = (N - N0) / WGS84_A * (180.0 / math.pi)
    dlon = (E - E0) / (WGS84_A * scale) * (180.0 / math.pi)
    return lat0 + dlat, lon0 + dlon


@dataclass
class NavPoint:
    timestamp_s: float
    lat: float
    lon: float
    heading_deg: float
    speed_mps: float
    altitude_m: float
    depth_m: float
    cable_out_m: float
    heave_m: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0


def generate_lawnmower(
    site: str = "CHENNAI_PORT",
    n_lines: int = 6,
    line_spacing_m: float = 50.0,
    line_length_m: float = 500.0,
    tow_speed_mps: float = 2.0,
    ping_rate_hz: float = 4.0,
    altitude_m: float = 5.0,
    depth_m: float = 15.0,
    cable_out_m: float = 30.0,
    heading_deg: float = 90.0,
    gps_noise_sigma_m: float = 2.0,
    rng: np.random.Generator | None = None,
) -> list[NavPoint]:
    """
    Generate a lawnmower survey pattern around a demo site.
    Returns a list of NavPoint objects (one per ping).
    """
    if rng is None:
        rng = np.random.default_rng()

    lat0, lon0 = DEMO_SITES.get(site, (13.10, 80.30))
    E0, N0 = lat_lon_to_utm_approx(lat0, lon0)

    nav_points: list[NavPoint] = []
    t = 0.0
    dt = 1.0 / ping_rate_hz
    dx_ping = tow_speed_mps * dt

    for line_idx in range(n_lines):
        # Alternate heading for lawnmower pattern
        line_heading = heading_deg if line_idx % 2 == 0 else (heading_deg + 180.0) % 360.0
        head_rad = math.radians(line_heading)

        # Start position of this line
        perp_rad = math.radians(heading_deg - 90.0)
        start_E = E0 + line_idx * line_spacing_m * math.cos(perp_rad)
        start_N = N0 + line_idx * line_spacing_m * math.sin(perp_rad)

        # If even line, start at near end; odd line at far end
        if line_idx % 2 == 1:
            start_E += line_length_m * math.cos(head_rad + math.pi)
            start_N += line_length_m * math.sin(head_rad + math.pi)

        n_pings = int(line_length_m / dx_ping)
        for ping_i in range(n_pings):
            E = start_E + ping_i * dx_ping * math.cos(head_rad)
            N = start_N + ping_i * dx_ping * math.sin(head_rad)

            # GPS noise
            E += rng.normal(0, gps_noise_sigma_m)
            N += rng.normal(0, gps_noise_sigma_m)

            lat, lon = utm_to_lat_lon_approx(E0, N0, E, N, lat0, lon0)

            # Attitude noise
            heave = rng.normal(0, 0.1)
            pitch = rng.normal(0, 1.0)
            roll = rng.normal(0, 1.5)

            nav_points.append(NavPoint(
                timestamp_s=t,
                lat=lat,
                lon=lon,
                heading_deg=line_heading,
                speed_mps=tow_speed_mps,
                altitude_m=altitude_m + rng.normal(0, 0.2),
                depth_m=depth_m,
                cable_out_m=cable_out_m,
                heave_m=heave,
                pitch_deg=pitch,
                roll_deg=roll,
            ))
            t += dt

    return nav_points
