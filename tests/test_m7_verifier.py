"""
Unit and integration tests for Milestone 7:
- Physics Verifier 8 rules (R1 to R8)
- Acoustic shadow height calculation
- Temperature scaling calibration and ECE
- Hazard Confidence fusion and operational triage
"""
import numpy as np
import pytest

from backend.sagarnetra.confidence.calibrate import TemperatureScaler, compute_ece
from backend.sagarnetra.confidence.fusion import ConfidenceFuser, HazardStatus
from backend.sagarnetra.verify.rules import PhysicsVerifier, calculate_height_from_shadow


def test_height_from_shadow_formula():
    """Validates h = (H * L_s) / (x_0 + L_s) acoustic geometry formula."""
    # H = 10m, x_0 = 30m, L_s = 6m -> h = 60 / 36 = 1.6667m
    h = calculate_height_from_shadow(altitude_m=10.0, ground_range_m=30.0, shadow_length_m=6.0)
    assert pytest.approx(h, abs=1e-3) == 1.667

    # Edge cases
    assert calculate_height_from_shadow(0.0, 30.0, 6.0) == 0.0
    assert calculate_height_from_shadow(10.0, 0.0, 6.0) == 0.0
    assert calculate_height_from_shadow(10.0, 30.0, 0.0) == 0.0


def test_physics_verifier_nominal_target():
    """Validates that a legitimate target passes all 8 acoustic physics rules."""
    verifier = PhysicsVerifier(horizontal_beamwidth_deg=0.4)

    res = verifier.verify(
        class_name="ghost_net",
        ground_range_m=25.0,
        altitude_m=8.0,
        slant_range_m=26.25,
        channel="stbd",
        highlight_extent_m=2.0,
        shadow_length_m=2.5,
        shadow_range_m=27.5,    # Far-range from highlight
        pings_persisted=5,
        local_slope_deg=2.0,
        mirror_detected=False,
    )

    assert res.passed is True
    assert res.v_phys > 0.5
    assert res.v_phys_norm > 0.75
    assert res.computed_height_m is not None
    assert 0.0 <= res.computed_height_m <= 1.5

    # Check that all rules returned positive scores
    for r in res.rule_results:
        assert r.score >= 0, f"Rule {r.rule_id} scored negative on valid target: {r.reason}"


def test_physics_verifier_anti_causal_shadow_rejection():
    """R2 check: shadow closer to nadir than highlight must trigger hard rejection."""
    verifier = PhysicsVerifier()

    res = verifier.verify(
        class_name="wreck_debris",
        ground_range_m=30.0,
        altitude_m=8.0,
        slant_range_m=31.0,
        shadow_length_m=3.0,
        shadow_range_m=25.0,    # Closer to nadir than highlight (impossible)
        pings_persisted=4,
    )

    r2 = next(r for r in res.rule_results if r.rule_id == "R2")
    assert r2.score == -1
    assert "Anti-causal" in r2.reason
    assert res.passed is False


def test_physics_verifier_mirror_crosstalk():
    """R3 check: symmetric echo on opposite channel is rejected as electrical/crosstalk."""
    verifier = PhysicsVerifier()

    res = verifier.verify(
        class_name="pipe",
        ground_range_m=20.0,
        altitude_m=6.0,
        slant_range_m=20.8,
        pings_persisted=3,
        mirror_detected=True,
    )

    r3 = next(r for r in res.rule_results if r.rule_id == "R3")
    assert r3.score == -1
    assert "crosstalk" in r3.reason.lower()
    assert res.passed is False


def test_physics_verifier_water_column_and_nadir():
    """R5 and R6 checks: pre-bottom echoes and nadir blind zone."""
    verifier = PhysicsVerifier()

    # Pre-bottom return in water column (slant range < altitude)
    res_water = verifier.verify(
        class_name="cylinder",
        ground_range_m=10.0,
        altitude_m=12.0,
        slant_range_m=6.0,      # Suspended at half depth
        pings_persisted=3,
    )
    r5 = next(r for r in res_water.rule_results if r.rule_id == "R5")
    assert r5.score == -1
    assert res_water.passed is False

    # Inside nadir blind zone (ground range < 1.0 m)
    res_nadir = verifier.verify(
        class_name="trap_pot",
        ground_range_m=0.4,
        altitude_m=8.0,
        slant_range_m=8.01,
        pings_persisted=3,
    )
    r6 = next(r for r in res_nadir.rule_results if r.rule_id == "R6")
    assert r6.score == -1
    assert res_nadir.passed is False


def test_temperature_scaling_and_ece():
    """Validates temperature fitting, calibrated probability mapping, and ECE computation."""
    np.random.seed(42)
    # Generate synthetic uncalibrated logits and targets
    logits = np.random.normal(loc=1.5, scale=2.0, size=200)
    # Ground truth with some miscalibration
    true_probs = 1.0 / (1.0 + np.exp(-logits * 0.5))
    targets = (np.random.uniform(0, 1, size=200) < true_probs).astype(float)

    uncal_probs = 1.0 / (1.0 + np.exp(-logits))
    uncal_ece = compute_ece(uncal_probs, targets)

    scaler = TemperatureScaler()
    opt_t = scaler.fit(logits, targets)
    assert opt_t > 0.0

    cal_probs = 1.0 / (1.0 + np.exp(-logits / opt_t))
    cal_ece = compute_ece(cal_probs, targets)

    assert "ece" in cal_ece
    assert "brier_score" in cal_ece
    assert cal_ece["ece"] <= uncal_ece["ece"] + 0.05
    assert len(cal_ece["bins"]) == 10


def test_confidence_fusion_statuses():
    """Validates Hazard Confidence formula and status categorization."""
    fuser = ConfidenceFuser()

    # Confirmed hazard: high probability, positive physics, good quality
    conf_high = fuser.compute_hazard_confidence(
        class_name="ghost_net",
        calibrated_prob=0.88,
        v_phys=0.75,
        q_obs=1.0,
        s_net=0.80,
        views=2,
        r95_m=2.5,
    )
    assert conf_high.score >= 60.0
    assert conf_high.status == HazardStatus.CONFIRMED_HAZARD
    assert conf_high.priority > 0.5

    # Suspected hazard: marginal evidence
    conf_sus = fuser.compute_hazard_confidence(
        class_name="cylinder",
        calibrated_prob=0.45,
        v_phys=0.1,
        q_obs=0.7,
        s_net=0.0,
        views=1,
    )
    assert 35.0 <= conf_sus.score < 60.0
    assert conf_sus.status == HazardStatus.SUSPECTED_HAZARD

    # Confuser rejection: natural seabed class suppressed
    conf_confuser = fuser.compute_hazard_confidence(
        class_name="sand_ripple",
        calibrated_prob=0.90,
        v_phys=0.8,
        q_obs=1.0,
    )
    assert conf_confuser.status == HazardStatus.CONFUSER_REJECTED

    # Insufficient evidence: severe quality impairment
    conf_bad = fuser.compute_hazard_confidence(
        class_name="pipe",
        calibrated_prob=0.75,
        v_phys=0.5,
        q_obs=0.15,  # Very low quality (burst dropout / altitude jump)
    )
    assert conf_bad.status == HazardStatus.INSUFFICIENT_EVIDENCE

    # Sensitive zone priority multiplier
    conf_normal = fuser.compute_hazard_confidence(
        class_name="wreck_debris", calibrated_prob=0.8, v_phys=0.6, in_sensitive_zone=False
    )
    conf_sensitive = fuser.compute_hazard_confidence(
        class_name="wreck_debris", calibrated_prob=0.8, v_phys=0.6, in_sensitive_zone=True
    )
    assert pytest.approx(conf_sensitive.priority, abs=1e-3) == conf_normal.priority * 1.5
