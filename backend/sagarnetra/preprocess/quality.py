"""
SagarNetra Preprocessing — Quality and Noise Flagging.
Detects dropouts, altitude jumps, navigation gaps, and excessive motion.
Interpolates single-ping dropouts and marks multi-ping bursts as NO_DATA.
"""
from __future__ import annotations

from typing import List, Tuple
import numpy as np

from backend.sagarnetra.io.schema import Ping, PingFlags


def detect_ping_quality(
    pings: List[Ping],
    energy_percentile_threshold: float = 5.0,
    max_alt_jump_m: float = 0.5,
    max_nav_gap_s: float = 2.0,
    max_attitude_deg: float = 10.0,
    max_attitude_rate_deg_s: float = 10.0,
) -> List[PingFlags]:
    """
    Evaluates quality flags for a sequence of pings.
    
    Flags evaluated per ping:
    - dropout: ping is all zeros, constant, or energy < 5th percentile of survey
    - altitude_jump: altitude differs by > max_alt_jump_m from previous ping
    - nav_missing: GPS missing, lat/lon == 0, or gap > max_nav_gap_s
    - attitude_excess: pitch/roll > max_attitude_deg or angular rate > max_attitude_rate_deg_s
    """
    if not pings:
        return []

    n = len(pings)
    flags_list: List[PingFlags] = []

    # Compute energy distribution across pings for both channels
    energies = np.zeros(n, dtype=np.float32)
    for i, p in enumerate(pings):
        p_arr = np.asarray(p.port, dtype=np.float32)
        s_arr = np.asarray(p.stbd, dtype=np.float32)
        e = float(np.mean(p_arr**2) + np.mean(s_arr**2)) if (len(p_arr) > 0 and len(s_arr) > 0) else 0.0
        energies[i] = e

    pos_energies = energies[energies > 0]
    e_thresh = float(np.percentile(pos_energies, energy_percentile_threshold)) if len(pos_energies) > 0 else 0.0

    for i in range(n):
        p = pings[i]
        p_arr = np.asarray(p.port)
        s_arr = np.asarray(p.stbd)

        # 1. Dropout check
        is_all_zero = (len(p_arr) == 0 or np.all(p_arr == 0)) and (len(s_arr) == 0 or np.all(s_arr == 0))
        is_stuck = (
            len(p_arr) > 1
            and np.all(p_arr == p_arr[0])
            and (p_arr[0] == 0 or p_arr[0] >= 65530)
        )
        is_low_energy = energies[i] < max(e_thresh * 0.1, 1e-4)
        dropout = bool(is_all_zero or is_stuck or (is_low_energy and energies[i] == 0))

        # 2. Altitude jump check
        alt_jump = False
        if i > 0:
            d_alt = abs(p.altitude_m - pings[i - 1].altitude_m)
            if d_alt > max_alt_jump_m:
                alt_jump = True

        # 3. Nav gap / missing check
        nav_missing = False
        if p.ship_lat == 0.0 and p.ship_lon == 0.0:
            nav_missing = True
        elif i > 0:
            dt = p.timestamp_utc - pings[i - 1].timestamp_utc
            if dt > max_nav_gap_s:
                nav_missing = True

        # 4. Attitude excess check
        attitude_excess = False
        if abs(p.roll_deg) > max_attitude_deg or abs(p.pitch_deg) > max_attitude_deg:
            attitude_excess = True
        elif i > 0:
            dt = max(p.timestamp_utc - pings[i - 1].timestamp_utc, 1e-3)
            d_roll_rate = abs(p.roll_deg - pings[i - 1].roll_deg) / dt
            d_pitch_rate = abs(p.pitch_deg - pings[i - 1].pitch_deg) / dt
            if d_roll_rate > max_attitude_rate_deg_s or d_pitch_rate > max_attitude_rate_deg_s:
                attitude_excess = True

        flag = PingFlags(
            dropout=dropout,
            nav_missing=nav_missing,
            altitude_jump=alt_jump,
            attitude_excess=attitude_excess,
        )
        flags_list.append(flag)

    return flags_list


def clean_dropouts(
    port_waterfall: np.ndarray,
    stbd_waterfall: np.ndarray,
    flags: List[PingFlags],
    burst_threshold: int = 4,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Cleans dropout pings in the waterfall matrices (shape: [num_pings, num_samples]):
    - Isolated single or dual dropouts (run length < burst_threshold) are linearly interpolated
      from surrounding valid pings.
    - Bursts (run length >= burst_threshold) are flagged as NO_DATA in no_data_mask (boolean array).
    
    Returns:
        cleaned_port: np.ndarray
        cleaned_stbd: np.ndarray
        no_data_mask: np.ndarray (shape [num_pings], True where data is unrecoverable)
    """
    n_pings = len(flags)
    port_out = port_waterfall.copy().astype(np.float32)
    stbd_out = stbd_waterfall.copy().astype(np.float32)
    no_data_mask = np.zeros(n_pings, dtype=bool)

    dropout_indices = [i for i, f in enumerate(flags) if f.dropout]
    if not dropout_indices:
        return port_out.astype(np.uint16), stbd_out.astype(np.uint16), no_data_mask

    runs: List[List[int]] = []
    current_run: List[int] = [dropout_indices[0]]

    for idx in dropout_indices[1:]:
        if idx == current_run[-1] + 1:
            current_run.append(idx)
        else:
            runs.append(current_run)
            current_run = [idx]
    runs.append(current_run)

    for run in runs:
        run_len = len(run)
        if run_len >= burst_threshold:
            for idx in run:
                no_data_mask[idx] = True
        else:
            prev_idx = run[0] - 1
            next_idx = run[-1] + 1

            if prev_idx >= 0 and next_idx < n_pings:
                p_prev, p_next = port_out[prev_idx], port_out[next_idx]
                s_prev, s_next = stbd_out[prev_idx], stbd_out[next_idx]
                total_steps = run_len + 1
                for step, idx in enumerate(run, 1):
                    alpha = step / total_steps
                    port_out[idx] = (1.0 - alpha) * p_prev + alpha * p_next
                    stbd_out[idx] = (1.0 - alpha) * s_prev + alpha * s_next
            elif prev_idx >= 0:
                for idx in run:
                    port_out[idx] = port_out[prev_idx]
                    stbd_out[idx] = stbd_out[prev_idx]
            elif next_idx < n_pings:
                for idx in run:
                    port_out[idx] = port_out[next_idx]
                    stbd_out[idx] = stbd_out[next_idx]

    return (
        np.clip(port_out, 0, 65535).astype(np.uint16),
        np.clip(stbd_out, 0, 65535).astype(np.uint16),
        no_data_mask,
    )
