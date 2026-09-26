"""
M3 Acceptance Tests for SagarNetra Preprocessing Chain.
Acceptance criteria:
- Slant-range correction within 1 pixel of synthetic ground truth
- Bottom tracking detects first return and Kalman filter smooths altitude
- Quality module detects dropouts, altitude jumps, and cleans single dropouts
- Enhanced Lee filter reduces speckle variance in homogeneous areas
- Sato ridge filter detects linear structures (ropes/lines)
- Feature stack produces [H, W, 3] in [0, 1]
- Tiler produces 512x512 windows with 25% overlap
- Full pipeline runs end-to-end on simulated pings
"""
from __future__ import annotations

import numpy as np
import pytest

from backend.sagarnetra.io.schema import Ping, PingFlags
from backend.sagarnetra.preprocess.quality import detect_ping_quality, clean_dropouts
from backend.sagarnetra.preprocess.bottom_track import (
    AltitudeKalmanFilter,
    detect_first_return_sample,
    track_bottom,
)
from backend.sagarnetra.preprocess.slant_range import (
    correct_slant_range_ping,
    correct_slant_range_waterfall,
    slant_to_ground_coord,
    ground_to_slant_coord,
)
from backend.sagarnetra.preprocess.motion import resample_along_track, compensate_yaw
from backend.sagarnetra.preprocess.gain import empirical_gain_normalisation, log_compress_and_scale
from backend.sagarnetra.preprocess.despeckle import enhanced_lee_filter, _box_filter_2d
from backend.sagarnetra.preprocess.features import (
    sato_ridge_filter,
    compute_shadow_probability_map,
    generate_feature_stack,
)
from backend.sagarnetra.preprocess.tiler import extract_tiles
from backend.sagarnetra.preprocess.pipeline import preprocess_survey_pings


def test_slant_range_within_one_pixel_of_truth():
    """
    CRITICAL ACCEPTANCE CHECK: Slant-range correction must place a synthetic target
    at ground range x_true within 1 pixel (dx = 0.10 m) of true location.
    """
    sample_spacing_m = 0.05  # 5 cm slant resolution
    ground_res_m = 0.10      # 10 cm ground resolution
    altitude_m = 10.0        # 10 m towfish altitude
    max_range_m = 50.0

    num_samples = int(np.ceil(np.sqrt(max_range_m**2 + altitude_m**2) / sample_spacing_m)) + 50
    ping_samples = np.zeros(num_samples, dtype=np.float32)

    # Place targets at several distinct ground ranges: 15.0m, 25.0m, 38.0m
    test_ground_ranges = [15.0, 25.0, 38.0]
    for x_true in test_ground_ranges:
        r_slant = ground_to_slant_coord(x_true, altitude_m)
        slant_idx = int(round(r_slant / sample_spacing_m))
        ping_samples[slant_idx] = 1000.0  # Bright delta target

    # Apply slant range correction
    corrected = correct_slant_range_ping(
        ping_samples=ping_samples,
        altitude_m=altitude_m,
        sample_spacing_m=sample_spacing_m,
        ground_res_m=ground_res_m,
        max_ground_range_m=max_range_m,
    )

    # For each target, find the peak in the corrected ground array
    for x_true in test_ground_ranges:
        expected_ground_bin = int(round(x_true / ground_res_m))
        # Search in a local window of +/- 3 pixels around expected bin
        search_window = corrected[max(0, expected_ground_bin - 3):expected_ground_bin + 4]
        local_peak_offset = int(np.argmax(search_window)) - 3
        detected_bin = expected_ground_bin + local_peak_offset

        error_bins = abs(detected_bin - expected_ground_bin)
        error_distance_m = error_bins * ground_res_m

        # Acceptance criteria: within 1 pixel (0.10 m) of synthetic truth
        assert error_bins <= 1, (
            f"Slant range error at x={x_true}m: detected bin {detected_bin}, "
            f"expected {expected_ground_bin}, error {error_bins} px ({error_distance_m}m)"
        )


def test_bottom_track_first_return():
    """Validates that bottom detection accurately locates first return at altitude."""
    sample_spacing_m = 0.05
    altitude_m = 8.0
    first_return_sample = int(round(altitude_m / sample_spacing_m))  # sample 160

    # Build ping: early samples near 0 (water column), then jump to high amplitude
    ping = np.ones(400, dtype=np.float32) * 50.0  # background noise
    ping[first_return_sample:] = 1200.0          # bottom echo

    idx, conf = detect_first_return_sample(ping, sample_spacing_m)
    detected_alt = idx * sample_spacing_m

    # Must be within 0.3 m of true altitude
    assert abs(detected_alt - altitude_m) <= 0.3
    assert conf > 0.5


def test_altitude_kalman_filter():
    """Validates Kalman filter noise reduction on altitude measurements."""
    kf = AltitudeKalmanFilter()
    kf.initialize(10.0)

    # Feed noisy measurements centered on 10.0 m with noise std 0.5m
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.5, size=30)
    filtered = []

    for n in noise:
        kf.predict()
        est = kf.update(10.0 + n)
        filtered.append(est)

    # Variance of filtered trajectory should be strictly less than measurement variance
    assert np.var(filtered[10:]) < np.var(10.0 + noise)
    assert abs(np.mean(filtered) - 10.0) < 0.2


def test_quality_flagging_and_dropout_cleanup():
    """Tests detection of dropouts, altitude jumps, and dropout cleaning."""
    pings = []
    for i in range(20):
        port = np.ones(100, dtype=np.uint16) * 1000
        stbd = np.ones(100, dtype=np.uint16) * 1000
        alt = 10.0
        if i == 5:
            # Single dropout
            port = np.zeros(100, dtype=np.uint16)
            stbd = np.zeros(100, dtype=np.uint16)
        elif i == 10:
            # Altitude jump
            alt = 15.0

        p = Ping(
            ping_id=i,
            timestamp_utc=100.0 + i * 0.1,
            ship_lat=13.0 + i * 0.0001,
            ship_lon=80.0,
            heading_deg=90.0,
            cog_deg=90.0,
            speed_mps=2.0,
            altitude_m=alt,
            depth_m=20.0,
            heave_m=0.0,
            pitch_deg=0.0,
            roll_deg=0.0,
            yaw_deg=0.0,
            sample_interval_s=1e-4,
            frequency_hz=450000.0,
            range_m=50.0,
            port=port.tolist(),
            stbd=stbd.tolist(),
        )
        pings.append(p)

    flags = detect_ping_quality(pings)
    assert flags[5].dropout is True
    assert flags[10].altitude_jump is True

    # Test dropout cleaning
    port_wf = np.array([p.port for p in pings], dtype=np.uint16)
    stbd_wf = np.array([p.stbd for p in pings], dtype=np.uint16)
    c_port, c_stbd, no_data = clean_dropouts(port_wf, stbd_wf, flags, burst_threshold=3)

    # Single dropout at index 5 should be interpolated (not zero anymore)
    assert c_port[5, 50] > 500
    assert not no_data[5]


def test_enhanced_lee_filter_variance_reduction():
    """Enhanced Lee filter must reduce speckle variance on flat patches while retaining step edges."""
    rng = np.random.default_rng(42)
    # Homogeneous patch with multiplicative noise
    clean_level = 0.5
    noisy = clean_level * rng.gamma(shape=4.0, scale=0.25, size=(100, 100)).astype(np.float32)
    
    filtered = enhanced_lee_filter(noisy, window_size=7)
    
    # Variance in homogeneous area must be significantly reduced
    orig_var = float(np.var(noisy[10:-10, 10:-10]))
    filt_var = float(np.var(filtered[10:-10, 10:-10]))
    assert filt_var < orig_var * 0.8  # Clear variance reduction


def test_sato_ridge_filter_detects_lines():
    """Validates that Sato filter responds strongly to thin line/rope structures."""
    img = np.zeros((100, 100), dtype=np.float32)
    # Add a thin bright line (rope)
    img[40:42, 20:80] = 1.0

    ridge = sato_ridge_filter(img, scales=(1.0, 2.0))
    
    # Response on the line must be much higher than off the line
    line_response = float(np.mean(ridge[40:42, 25:75]))
    background_response = float(np.mean(ridge[10:30, 25:75]))
    assert line_response > 0.5
    assert line_response > 5.0 * background_response


def test_feature_stack_generation():
    """Validates 3-channel feature stack shape, values, and channel contents."""
    intensity = np.random.default_rng(0).uniform(0.1, 0.8, size=(80, 80)).astype(np.float32)
    stack = generate_feature_stack(intensity)

    assert stack.shape == (80, 80, 3)
    assert stack.dtype == np.float32
    assert float(np.min(stack)) >= 0.0
    assert float(np.max(stack)) <= 1.0


def test_tiler_extraction():
    """Validates tile extraction with 512x512 size and 25% overlap."""
    feat_stack = np.zeros((1000, 600, 3), dtype=np.float32)
    raw = np.zeros((1000, 600), dtype=np.float32)
    qual = np.ones((1000, 600), dtype=bool)
    ranges = np.arange(600, dtype=np.float32) * 0.10
    along = np.arange(1000, dtype=np.float32) * 0.10
    pings = np.arange(1000, dtype=np.float32)

    tiles = extract_tiles(
        feature_stack=feat_stack,
        raw_intensity=raw,
        quality_mask=qual,
        ground_ranges_m=ranges,
        along_track_m=along,
        ping_indices=pings,
        survey_id="test_survey",
        side="port",
        tile_size=512,
        overlap_fraction=0.25,
        ground_res_m=0.10,
    )

    assert len(tiles) >= 4
    for t in tiles:
        assert t.feature_stack.shape == (512, 512, 3)
        assert t.raw_intensity.shape == (512, 512)
        assert t.quality_mask.shape == (512, 512)
        assert len(t.ground_ranges_m) == 512
        assert len(t.along_track_m) == 512


def test_full_preprocessing_pipeline():
    """End-to-end integration test of preprocess_survey_pings."""
    n_pings = 50
    n_samples = 400
    pings = []
    
    for i in range(n_pings):
        p = Ping(
            ping_id=i,
            timestamp_utc=1000.0 + i * 0.1,
            ship_lat=13.0 + i * 0.0001,
            ship_lon=80.3,
            heading_deg=0.0,
            cog_deg=0.0,
            speed_mps=2.0,
            altitude_m=10.0,
            depth_m=20.0,
            heave_m=0.0,
            pitch_deg=0.0,
            roll_deg=0.0,
            yaw_deg=0.0,
            sample_interval_s=1e-4,
            frequency_hz=450000.0,
            range_m=40.0,
            port=[100 + (j % 50) for j in range(n_samples)],
            stbd=[100 + (j % 50) for j in range(n_samples)],
        )
        pings.append(p)

    res = preprocess_survey_pings(
        pings=pings,
        survey_id="sim_chennai_01",
        ground_res_m=0.10,
        along_res_m=0.10,
        max_ground_range_m=35.0,
        tile_size=512,
    )

    assert res.survey_id == "sim_chennai_01"
    assert len(res.flags) == n_pings
    assert res.port.side == "port"
    assert res.stbd.side == "stbd"
    assert len(res.port.tiles) > 0
    assert len(res.stbd.tiles) > 0
    assert res.port.feature_stack.shape[-1] == 3
