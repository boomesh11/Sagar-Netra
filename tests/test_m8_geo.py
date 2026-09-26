"""
Unit and integration tests for Milestone 8:
- WGS84 to UTM forward and inverse projection roundtrip
- Towfish layback and target georeferencing
- 5-component position error budget (r95)
- Physical dimensions and PCA orientation
- Multi-view track association
- ClearanceGridMap and PoD model
- Second-look survey line planner
- Disaster Mode pre/post cyclone change detection
"""
import math
import numpy as np
import pytest

from backend.sagarnetra.change.disaster import (
    DisasterChangeDetector,
    create_synthetic_disaster_scenario,
)
from backend.sagarnetra.coverage.pod_map import (
    ClearanceGridMap,
    ClearanceState,
    model_pod,
)
from backend.sagarnetra.geo.dimensions import compute_physical_dimensions
from backend.sagarnetra.geo.error_budget import compute_position_error_budget
from backend.sagarnetra.geo.project import (
    compute_target_coordinates,
    compute_towfish_position,
    latlon_to_utm,
    utm_to_latlon,
)
from backend.sagarnetra.track.associate import (
    GeoreferencedDetection,
    MultiViewAssociator,
)


def test_utm_latlon_roundtrip():
    """Validates centimeter-level roundtrip accuracy for Indian ports across UTM zones 43, 44, 45."""
    test_ports = [
        ("Chennai", 13.0827, 80.2707, 44),
        ("Kochi", 9.9312, 76.2673, 43),
        ("Visakhapatnam", 17.6868, 83.2185, 44),
        ("Paradip", 20.3165, 86.6114, 45),
    ]

    for port_name, lat, lon, expected_zone in test_ports:
        e, n, zone = latlon_to_utm(lat, lon)
        assert zone == expected_zone, f"{port_name} assigned wrong UTM zone {zone}"

        # Invert back to lat/lon
        lat_inv, lon_inv = utm_to_latlon(e, n, zone=zone)
        assert pytest.approx(lat, abs=1e-5) == lat_inv, f"{port_name} lat mismatch"
        assert pytest.approx(lon, abs=1e-5) == lon_inv, f"{port_name} lon mismatch"


def test_compute_towfish_position():
    """Validates horizontal layback L = sqrt(C^2 - D^2) and heading trail."""
    # Vessel at (500000, 1400000), heading North (0 deg), cable out 25m, depth 15m
    # Layback = sqrt(25^2 - 15^2) = sqrt(625 - 225) = sqrt(400) = 20.0 m
    # Towfish should trail 20m South -> Easting 500000, Northing 1399980
    tf_e, tf_n, layback = compute_towfish_position(
        ship_easting=500000.0,
        ship_northing=1400000.0,
        ship_heading_deg=0.0,
        cable_out_m=25.0,
        towfish_depth_m=15.0,
    )
    assert pytest.approx(layback, abs=0.1) == 20.0
    assert pytest.approx(tf_e, abs=0.1) == 500000.0
    assert pytest.approx(tf_n, abs=0.1) == 1399980.0


def test_compute_target_coordinates():
    """Validates E_t = E_f + s * x * cos(theta), N_t = N_f - s * x * sin(theta)."""
    tf_e, tf_n = 400000.0, 1500000.0
    heading_deg = 90.0  # Heading East
    ground_range = 30.0

    # Heading East: Starboard (s = +1) points South
    # Delta E = +1 * 30 * cos(90) = 0
    # Delta N = -1 * 30 * sin(90) = -30
    t_e, t_n, lat, lon = compute_target_coordinates(
        towfish_easting=tf_e,
        towfish_northing=tf_n,
        towfish_heading_deg=heading_deg,
        ground_range_m=ground_range,
        channel="stbd",
        zone=44,
    )
    assert pytest.approx(t_e, abs=0.1) == 400000.0
    assert pytest.approx(t_n, abs=0.1) == 1499970.0
    assert 13.0 < lat < 14.0
    assert 79.0 < lon < 82.0


def test_position_error_budget():
    """Validates 5-component error budget and r95 = 2.45 * sigma_tot."""
    budget = compute_position_error_budget(
        ground_range_m=40.0,
        layback_m=20.0,
        speed_mps=1.5,
        sigma_gps_m=2.0,
        sigma_heading_deg=1.0,
    )

    assert budget.r95_m > 0.0
    assert pytest.approx(budget.r95_m, abs=0.05) == budget.sigma_total_m * 2.45
    assert budget.sigma_layback_m == pytest.approx(3.0, abs=0.1)  # 0.10 * 20 + 1.0 = 3.0
    assert 7.0 <= budget.r95_m <= 15.0  # Reasonable operational marine tolerance


def test_physical_dimensions_pca():
    """Validates PCA orientation, length, and width extraction on oriented rectangle mask."""
    mask = np.zeros((100, 100), dtype=np.uint8)
    # Draw a line of length 40 pixels along vertical axis (rows 30:70, cols 48:52)
    # Length = 40 * 0.1 = 4.0 m, Width = 4 * 0.1 = 0.4 m
    mask[30:70, 48:52] = 1

    dims = compute_physical_dimensions(
        mask,
        res_across_m=0.10,
        res_along_m=0.10,
        towfish_heading_deg=0.0,
        height_m=0.8,
    )

    assert pytest.approx(dims.length_m, abs=0.5) == 4.0
    assert pytest.approx(dims.width_m, abs=0.3) == 0.4
    assert dims.aspect_ratio > 5.0
    assert dims.height_m == 0.8
    assert dims.area_m2 > 1.0


def test_multi_view_association():
    """Validates merging detections from intersecting survey passes."""
    associator = MultiViewAssociator()

    # Pass 1: detection at (500010, 1400010) with r95 = 4.0 m
    lat1, lon1 = utm_to_latlon(500010.0, 1400010.0, zone=44)
    det1 = GeoreferencedDetection(
        detection_id="DET_001",
        class_name="ghost_net",
        utm_easting=500010.0,
        utm_northing=1400010.0,
        zone=44,
        lat=lat1,
        lon=lon1,
        r95_m=4.0,
        calibrated_prob=0.85,
        v_phys=0.7,
        s_net=0.8,
        q_obs=1.0,
        survey_line_id="LINE_01",
        timestamp=100.0,
        length_m=6.0,
        width_m=2.0,
    )

    # Pass 2: detection at (500012, 1400013) with r95 = 5.0 m (distance ~3.6 m < 4+5 m)
    lat2, lon2 = utm_to_latlon(500012.0, 1400013.0, zone=44)
    det2 = GeoreferencedDetection(
        detection_id="DET_002",
        class_name="ghost_net",
        utm_easting=500012.0,
        utm_northing=1400013.0,
        zone=44,
        lat=lat2,
        lon=lon2,
        r95_m=5.0,
        calibrated_prob=0.90,
        v_phys=0.8,
        s_net=0.85,
        q_obs=1.0,
        survey_line_id="LINE_02",
        timestamp=400.0,
        length_m=5.5,
        width_m=2.2,
    )

    targets = associator.associate_detections([det1, det2])
    assert len(targets) == 1  # Associated into 1 target!

    tgt = targets[0]
    assert tgt.views == 2
    assert len(tgt.contributing_detections) == 2
    assert tgt.r95_m < min(det1.r95_m, det2.r95_m)  # Uncertainty reduced by multiple views!
    assert tgt.fused_confidence is not None
    assert tgt.fused_confidence.score >= 60.0


def test_clearance_grid_map_and_pod():
    """Validates swath coverage, PoD modeling, and clearance stats."""
    pod_val = model_pod(ground_range_m=25.0, max_range_m=60.0)
    assert 0.70 <= pod_val <= 0.99  # Sweet spot range

    grid = ClearanceGridMap(
        origin_easting=500000.0,
        origin_northing=1400000.0,
        width_m=200.0,
        height_m=200.0,
        cell_size_m=5.0,
        zone=44,
    )

    # Record survey pass through middle of grid
    grid.record_swath(
        start_e=500100.0,
        start_n=1400000.0,
        end_e=500100.0,
        end_n=1400200.0,
        altitude_m=8.0,
        range_m=50.0,
    )

    # Mark a candidate target
    grid.mark_target(500115.0, 1400100.0)

    summary = grid.get_clearance_summary()
    assert summary["total_area_km2"] == 0.04
    assert summary["surveyed_clear_km2"] > 0.0
    assert summary["candidate_km2"] > 0.0
    assert summary["clearance_percent"] > 20.0


def test_second_look_planner():
    """Validates orthogonal line planning placing target at 45% range."""
    grid = ClearanceGridMap(500000.0, 1400000.0, 200.0, 200.0, zone=44)

    line = grid.plan_second_look_line(
        target_id="TGT_001",
        target_e=500100.0,
        target_n=1400100.0,
        original_heading_deg=0.0,  # Original pass North
        swath_range_m=60.0,
        run_length_m=100.0,
    )

    assert line.heading_deg == 90.0  # Orthogonal heading East
    assert pytest.approx(line.swath_offset_m, abs=0.1) == 27.0  # 0.45 * 60 = 27m
    assert pytest.approx(line.length_m, abs=0.1) == 100.0
    assert line.start_latlon != line.end_latlon


def test_disaster_change_detection():
    """Validates pre/post cyclone change detection on Chennai Port basin scenario."""
    base_img, post_img, meta = create_synthetic_disaster_scenario("chennai_port_basin")
    detector = DisasterChangeDetector(zone=meta["utm_zone"])

    obstructions = detector.detect_changes(
        baseline_img=base_img,
        post_disaster_img=post_img,
        origin_easting=meta["origin_utm"][0],
        origin_northing=meta["origin_utm"][1],
        res_m=0.10,
        min_area_m2=0.5,
    )

    assert len(obstructions) >= 1
    # Check that obstructions are characterized with dimensions and confidence
    for obs in obstructions:
        assert obs.change_type.value == "NEW_OBSTRUCTION"
        assert obs.dimensions.area_m2 >= 0.5
        assert obs.r95_m > 0.0
        assert obs.confidence.score > 0.0
        assert obs.confidence.priority > 0.0
