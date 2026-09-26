"""
SagarNetra Geotagging — UTM Projection, Towfish Layback, and Acoustic Georeferencing.
Converts side-scan sonar detection pixels to real-world WGS84 coordinates:
  - WGS84 <-> UTM forward and inverse projection (Zones 43N, 44N, 45N for Indian coastline)
  - Horizontal towfish layback calculation from cable payout and depth
  - Geometric across-track offset from towfish heading and ground range
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


# WGS84 Ellipsoid Constants
WGS84_A = 6378137.0          # Semi-major axis in metres
WGS84_F = 1.0 / 298.257223563 # Flattening
WGS84_B = WGS84_A * (1.0 - WGS84_F)
WGS84_E2 = (WGS84_A**2 - WGS84_B**2) / (WGS84_A**2)
WGS84_E_PRIME2 = (WGS84_A**2 - WGS84_B**2) / (WGS84_B**2)


def get_utm_zone_from_lon(longitude: float) -> int:
    """Returns UTM zone number (1-60). Indian waters: 43 (West), 44 (South/East), 45 (Bay of Bengal)."""
    return int((longitude + 180.0) / 6.0) + 1


def latlon_to_utm(lat: float, lon: float, zone: int | None = None) -> Tuple[float, float, int]:
    """
    Projects WGS84 latitude and longitude to UTM Easting and Northing (metres).
    Returns: (easting_m, northing_m, zone)
    """
    if zone is None:
        zone = get_utm_zone_from_lon(lon)

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    # Central meridian
    lon0 = (zone - 1) * 6 - 180 + 3
    lon0_rad = math.radians(lon0)

    k0 = 0.9996  # Scale factor

    n = WGS84_F / (2.0 - WGS84_F)
    a_bar = (WGS84_A / (1.0 + n)) * (1.0 + (n**2) / 4.0 + (n**4) / 64.0)

    # Meridian distance
    alpha1 = 1.0/2.0 * n - 2.0/3.0 * n**2 + 5.0/16.0 * n**3
    alpha2 = 13.0/48.0 * n**2 - 3.0/5.0 * n**3
    alpha3 = 61.0/240.0 * n**3

    delta_lon = lon_rad - lon0_rad

    t = math.sinh(math.atanh(math.sin(lat_rad)) - (2.0 * math.sqrt(n) / (1.0 + n)) * math.atanh((2.0 * math.sqrt(n) / (1.0 + n)) * math.sin(lat_rad)))
    xi_prime = math.atan(t / math.cos(delta_lon))
    eta_prime = math.atanh(math.sin(delta_lon) / math.sqrt(1.0 + t**2))

    xi = xi_prime + (
        alpha1 * math.sin(2.0 * xi_prime) * math.cosh(2.0 * eta_prime)
        + alpha2 * math.sin(4.0 * xi_prime) * math.cosh(4.0 * eta_prime)
        + alpha3 * math.sin(6.0 * xi_prime) * math.cosh(6.0 * eta_prime)
    )

    eta = eta_prime + (
        alpha1 * math.cos(2.0 * xi_prime) * math.sinh(2.0 * eta_prime)
        + alpha2 * math.cos(4.0 * xi_prime) * math.sinh(4.0 * eta_prime)
        + alpha3 * math.cos(6.0 * xi_prime) * math.sinh(6.0 * eta_prime)
    )

    easting = 500000.0 + k0 * a_bar * eta
    northing = k0 * a_bar * xi
    if lat < 0.0:
        northing += 10000000.0  # Southern hemisphere false northing

    return round(easting, 2), round(northing, 2), zone


def utm_to_latlon(easting: float, northing: float, zone: int, northern: bool = True) -> Tuple[float, float]:
    """
    Inverse UTM projection: converts UTM Easting and Northing to WGS84 (lat, lon) in degrees.
    """
    k0 = 0.9996
    lon0 = (zone - 1) * 6 - 180 + 3
    lon0_rad = math.radians(lon0)

    n = WGS84_F / (2.0 - WGS84_F)
    a_bar = (WGS84_A / (1.0 + n)) * (1.0 + (n**2) / 4.0 + (n**4) / 64.0)

    beta1 = 1.0/2.0 * n - 2.0/3.0 * n**2 + 37.0/96.0 * n**3
    beta2 = 1.0/48.0 * n**2 + 1.0/15.0 * n**3
    beta3 = 17.0/480.0 * n**3

    xi = (northing if northern else (northing - 10000000.0)) / (k0 * a_bar)
    eta = (easting - 500000.0) / (k0 * a_bar)

    xi_prime = xi - (
        beta1 * math.sin(2.0 * xi) * math.cosh(2.0 * eta)
        + beta2 * math.sin(4.0 * xi) * math.cosh(4.0 * eta)
        + beta3 * math.sin(6.0 * xi) * math.cosh(6.0 * eta)
    )

    eta_prime = eta - (
        beta1 * math.cos(2.0 * xi) * math.sinh(2.0 * eta)
        + beta2 * math.cos(4.0 * xi) * math.sinh(4.0 * eta)
        + beta3 * math.cos(6.0 * xi) * math.sinh(6.0 * eta)
    )

    chi = math.asin(math.sin(xi_prime) / math.cosh(eta_prime))
    lat_rad = chi + (
        (2.0 * n - 2.0/3.0 * n**2 - 2.0 * n**3) * math.sin(2.0 * chi)
        + (7.0/3.0 * n**2 - 8.0/5.0 * n**3) * math.sin(4.0 * chi)
        + (56.0/15.0 * n**3) * math.sin(6.0 * chi)
    )

    delta_lon = math.atan(math.sinh(eta_prime) / math.cos(xi_prime))
    lon_rad = lon0_rad + delta_lon

    lat = math.degrees(lat_rad)
    lon = math.degrees(lon_rad)
    return round(lat, 7), round(lon, 7)


def compute_towfish_position(
    ship_easting: float,
    ship_northing: float,
    ship_heading_deg: float,
    cable_out_m: float,
    towfish_depth_m: float,
) -> Tuple[float, float, float]:
    """
    Calculates horizontal towfish position trailing behind vessel.
    Returns: (towfish_easting, towfish_northing, horizontal_layback_m)
    """
    # Horizontal layback = sqrt(cable_out^2 - depth^2)
    layback_m = math.sqrt(max(0.0, cable_out_m**2 - towfish_depth_m**2))
    heading_rad = math.radians(ship_heading_deg)

    # Towfish trails in opposite direction of heading
    # Heading 0 deg (North) -> trailing to South (Delta N = -layback, Delta E = 0)
    tf_easting = ship_easting - layback_m * math.sin(heading_rad)
    tf_northing = ship_northing - layback_m * math.cos(heading_rad)

    return round(tf_easting, 2), round(tf_northing, 2), round(layback_m, 2)


def compute_target_coordinates(
    towfish_easting: float,
    towfish_northing: float,
    towfish_heading_deg: float,
    ground_range_m: float,
    channel: str,  # "port" or "stbd"
    zone: int = 44,
) -> Tuple[float, float, float, float]:
    """
    Computes real-world target coordinates from towfish position and across-track offset.
    
    Formula from Chapter 10:
        E_t = E_f + s * x * cos(heading)
        N_t = N_f - s * x * sin(heading)
    where s = +1 for starboard and -1 for port.
    
    Returns:
        (target_easting, target_northing, target_lat, target_lon)
    """
    s = +1.0 if channel.lower() in ["stbd", "starboard"] else -1.0
    heading_rad = math.radians(towfish_heading_deg)

    target_easting = towfish_easting + s * ground_range_m * math.cos(heading_rad)
    target_northing = towfish_northing - s * ground_range_m * math.sin(heading_rad)

    lat, lon = utm_to_latlon(target_easting, target_northing, zone=zone)
    return round(target_easting, 2), round(target_northing, 2), lat, lon
