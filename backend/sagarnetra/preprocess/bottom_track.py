"""
SagarNetra Preprocessing — Bottom Track & Altitude Estimation.
Detects first seabed return per side using smoothed energy gradients,
smooths altitude with a 1D Kalman filter, and cross-checks with header altitude.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np


@dataclass
class BottomTrackResult:
    estimated_altitudes_m: np.ndarray      # Shape: [num_pings], Kalman-smoothed altitude (m)
    raw_first_returns_port_m: np.ndarray   # Shape: [num_pings], Port first return slant range (m)
    raw_first_returns_stbd_m: np.ndarray   # Shape: [num_pings], Starboard first return slant range (m)
    disagreement_flags: np.ndarray         # Shape: [num_pings], True if header vs tracked altitude > max_diff
    confidence: np.ndarray                 # Shape: [num_pings], Confidence score [0.0, 1.0]


class AltitudeKalmanFilter:
    """
    1D Constant Velocity Kalman Filter for tracking towfish altitude across pings.
    State x = [altitude (m), vertical velocity (m/ping)]^T.
    """
    def __init__(self, q_alt: float = 0.05, q_vel: float = 0.01, r_meas: float = 0.3):
        self.q_alt = q_alt
        self.q_vel = q_vel
        self.r_meas = r_meas
        self.x = np.zeros(2, dtype=np.float64)  # [h, v]
        self.P = np.diag([1.0, 0.5])            # State covariance
        self.initialized = False

    def initialize(self, init_alt: float):
        self.x[0] = init_alt
        self.x[1] = 0.0
        self.P = np.diag([0.5, 0.2])
        self.initialized = True

    def predict(self):
        # F = [[1, 1], [0, 1]]
        self.x[0] += self.x[1]
        self.P[0, 0] += 2 * self.P[0, 1] + self.P[1, 1] + self.q_alt
        self.P[0, 1] += self.P[1, 1]
        self.P[1, 0] = self.P[0, 1]
        self.P[1, 1] += self.q_vel

    def update(self, z: float, r_variance: Optional[float] = None) -> float:
        r = r_variance if r_variance is not None else self.r_meas
        # Innovation y = z - Hx (H = [1, 0])
        y = z - self.x[0]
        S = self.P[0, 0] + r
        K = np.array([self.P[0, 0] / S, self.P[1, 0] / S], dtype=np.float64)

        self.x += K * y
        # P = (I - K*H) * P
        I_KH = np.array([[1.0 - K[0], 0.0], [-K[1], 1.0]], dtype=np.float64)
        self.P = I_KH @ self.P
        return float(self.x[0])


def detect_first_return_sample(
    ping_samples: np.ndarray,
    sample_spacing_m: float,
    min_range_m: float = 1.0,
    search_window: int = 15,
    threshold_factor: float = 3.5,
) -> Tuple[int, float]:
    """
    Finds the first bottom echo sample along a single sonar channel.
    Uses smoothed forward energy derivative and background noise estimation.
    
    Returns:
        (sample_index, confidence in [0, 1])
    """
    n = len(ping_samples)
    min_idx = max(int(min_range_m / sample_spacing_m), 1)
    if n <= min_idx + search_window:
        return min_idx, 0.0

    # Compute baseline water column noise floor in early bins
    water_column = ping_samples[1:min_idx].astype(np.float32)
    noise_floor = float(np.median(water_column)) if len(water_column) > 0 else 100.0
    noise_std = float(np.std(water_column)) if len(water_column) > 0 else 50.0
    noise_std = max(noise_std, 10.0)

    # Compute smoothed gradient
    smooth = np.convolve(ping_samples.astype(np.float32), np.ones(5) / 5.0, mode="same")
    grad = np.diff(smooth)

    # Search for gradient peak where intensity exceeds threshold
    detect_thresh = noise_floor + threshold_factor * noise_std
    for i in range(min_idx, n - search_window):
        if smooth[i] > detect_thresh and grad[i] > noise_std:
            # Check persistence in window
            if np.mean(smooth[i:i + search_window]) > detect_thresh * 0.8:
                conf = min(float((smooth[i] - noise_floor) / (3.0 * noise_std + 1e-5)), 1.0)
                return i, max(conf, 0.2)

    # Fallback to absolute maximum if gradient didn't trigger cleanly
    max_idx = int(np.argmax(smooth[min_idx:])) + min_idx
    return max_idx, 0.1


def track_bottom(
    port_waterfall: np.ndarray,
    stbd_waterfall: np.ndarray,
    header_altitudes: np.ndarray,
    sample_spacing_m: float,
    sound_speed_mps: float = 1500.0,
    max_header_diff_m: float = 1.0,
) -> BottomTrackResult:
    """
    Acoustic bottom tracking across both channels for all pings.
    Combines port and starboard first returns with Kalman smoothing.
    """
    n_pings, n_samples = port_waterfall.shape
    est_alts = np.zeros(n_pings, dtype=np.float32)
    port_alts = np.zeros(n_pings, dtype=np.float32)
    stbd_alts = np.zeros(n_pings, dtype=np.float32)
    disagree = np.zeros(n_pings, dtype=bool)
    confs = np.zeros(n_pings, dtype=np.float32)

    kf = AltitudeKalmanFilter()

    # Determine initial altitude estimate
    init_alt = float(header_altitudes[0]) if len(header_altitudes) > 0 and header_altitudes[0] > 0.5 else 10.0
    kf.initialize(init_alt)

    for i in range(n_pings):
        p_idx, p_conf = detect_first_return_sample(port_waterfall[i], sample_spacing_m)
        s_idx, s_conf = detect_first_return_sample(stbd_waterfall[i], sample_spacing_m)

        r_port = p_idx * sample_spacing_m
        r_stbd = s_idx * sample_spacing_m
        port_alts[i] = r_port
        stbd_alts[i] = r_stbd

        hdr_alt = float(header_altitudes[i]) if i < len(header_altitudes) else 0.0

        # Weighted combination of port, starboard, and header
        tot_conf = p_conf + s_conf
        if tot_conf > 0.3:
            meas_alt = (r_port * p_conf + r_stbd * s_conf) / tot_conf
            r_var = 0.2 / max(tot_conf, 0.1)
        elif hdr_alt > 0.5:
            meas_alt = hdr_alt
            r_var = 0.5
            tot_conf = 0.5
        else:
            meas_alt = kf.x[0]  # Coast on prior
            r_var = 2.0
            tot_conf = 0.1

        kf.predict()
        tracked = kf.update(meas_alt, r_variance=r_var)
        est_alts[i] = tracked
        confs[i] = min(tot_conf, 1.0)

        # Check disagreement with header
        if hdr_alt > 0.5:
            diff = abs(tracked - hdr_alt)
            if diff > max_header_diff_m and diff / max(hdr_alt, 1e-3) > 0.2:
                disagree[i] = True

    return BottomTrackResult(
        estimated_altitudes_m=est_alts,
        raw_first_returns_port_m=port_alts,
        raw_first_returns_stbd_m=stbd_alts,
        disagreement_flags=disagree,
        confidence=confs,
    )
