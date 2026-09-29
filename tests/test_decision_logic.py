"""
tests/test_decision_logic.py
============================
Unit tests for EchoSift Stage 3 Verification & Decision Logic.
Tests hand-built evidence vectors covering every decision outcome:
1. wreck
2. pipe_cylinder
3. net_debris
4. other_manmade
5. unknown_manmade (e.g. bicycle case)
6. natural_suppressed (sand ripples, anti-causal shadow, flat sediment)
7. uncertain (low confidence, high motion corruption)
"""
import pytest
from backend.sagarnetra.verify.decision import decide_target


def test_outcome_natural_suppressed_sand_ripples():
    """Verify widespread periodic texture in annulus suppresses candidate as natural sand ripple."""
    res = decide_target(
        cnn_score=0.85,
        shc_score=0.80,
        regularity_score=0.20,
        motion_penalty=0.0,
        persistence_score=0.50,
        shadow_side="correct",
        height_estimate_m=0.3,
        is_sand_ripple=True,
        annular_contrast=0.10,
    )
    assert res.decision == "natural_suppressed"
    assert res.class_name == "natural_suppressed"
    assert res.suppressed is True
    assert "sand ripples" in res.decision_reason.lower()


def test_outcome_natural_suppressed_anti_causal_shadow():
    """Verify anti-causal shadow pointing toward nadir is suppressed."""
    res = decide_target(
        cnn_score=0.75,
        shc_score=0.10,
        regularity_score=0.50,
        motion_penalty=0.0,
        persistence_score=0.50,
        shadow_side="incorrect",
        height_estimate_m=0.0,
        is_sand_ripple=False,
    )
    assert res.decision == "natural_suppressed"
    assert res.suppressed is True
    assert "toward nadir" in res.decision_reason.lower()


def test_outcome_natural_suppressed_flat_feature():
    """Verify flat sediment variation with no shadow and zero relief is suppressed."""
    res = decide_target(
        cnn_score=0.40,
        shc_score=0.10,
        regularity_score=0.20,
        motion_penalty=0.0,
        persistence_score=0.50,
        shadow_side="correct",
        height_estimate_m=0.02,
        is_sand_ripple=False,
        has_shadow=False,
        anomaly_score=0.20,
    )
    assert res.decision == "natural_suppressed"
    assert res.suppressed is True
    assert "flat acoustic feature" in res.decision_reason.lower()


def test_outcome_uncertain_motion_corrupted():
    """Verify > 40% overlap with data quality mask routes to uncertain."""
    res = decide_target(
        cnn_score=0.85,
        shc_score=0.85,
        regularity_score=0.70,
        motion_penalty=0.50,
        persistence_score=0.50,
        shadow_side="correct",
        height_estimate_m=1.0,
        is_sand_ripple=False,
        quality_overlap_pct=52.0,
    )
    assert res.decision == "uncertain"
    assert "corruption" in res.decision_reason.lower()


def test_outcome_uncertain_low_confidence():
    """Verify candidate below confidence threshold routes to uncertain."""
    res = decide_target(
        cnn_score=0.15,
        shc_score=0.20,
        regularity_score=0.20,
        motion_penalty=0.30,
        persistence_score=0.20,
        shadow_side="correct",
        height_estimate_m=0.2,
        is_sand_ripple=False,
    )
    assert res.decision == "uncertain"
    assert res.confidence < 40.0
    assert "below verification threshold" in res.decision_reason.lower()


def test_outcome_net_debris():
    """Verify amorphous texture + thin ridges + mesh floats + low relief = net_debris."""
    res = decide_target(
        cnn_score=0.80,
        shc_score=0.85,
        regularity_score=0.45,
        motion_penalty=0.0,
        persistence_score=0.60,
        shadow_side="correct",
        height_estimate_m=0.75,
        is_sand_ripple=False,
        s_net=0.68,
        dims_px=(25.0, 20.0),
    )
    assert res.decision == "net_debris"
    assert res.class_name == "net_debris"
    assert res.suppressed is False
    assert "net signature detected" in res.decision_reason.lower()


def test_outcome_wreck():
    """Verify large rigid structure with prominent relief is classed as wreck."""
    res = decide_target(
        cnn_score=0.90,
        shc_score=0.95,
        regularity_score=0.55,
        motion_penalty=0.0,
        persistence_score=0.80,
        shadow_side="correct",
        height_estimate_m=2.8,
        is_sand_ripple=False,
        s_net=0.15,
        dims_px=(65.0, 28.0),
        merged_count=3,
    )
    assert res.decision == "wreck"
    assert res.class_name == "wreck"
    assert res.suppressed is False
    assert "wreck structure" in res.decision_reason.lower()


def test_outcome_pipe_cylinder():
    """Verify high linear aspect ratio with straight parallel shadow = pipe_cylinder."""
    res = decide_target(
        cnn_score=0.85,
        shc_score=0.90,
        regularity_score=0.78,
        motion_penalty=0.0,
        persistence_score=0.60,
        shadow_side="correct",
        height_estimate_m=0.6,
        is_sand_ripple=False,
        s_net=0.10,
        dims_px=(70.0, 12.0),  # aspect ratio > 5.0
    )
    assert res.decision == "pipe_cylinder"
    assert res.class_name == "pipe_cylinder"
    assert res.suppressed is False
    assert "cylindrical" in res.decision_reason.lower()


def test_outcome_other_manmade():
    """Verify highly regular manufactured geometric object = other_manmade."""
    res = decide_target(
        cnn_score=0.88,
        shc_score=0.85,
        regularity_score=0.82,
        motion_penalty=0.0,
        persistence_score=0.60,
        shadow_side="correct",
        height_estimate_m=1.1,
        is_sand_ripple=False,
        s_net=0.10,
        anthropogenic_score=0.85,
        dims_px=(25.0, 22.0),
    )
    assert res.decision == "other_manmade"
    assert res.class_name == "other_manmade"
    assert res.suppressed is False
    assert "manufactured geometric structure" in res.decision_reason.lower()


def test_outcome_unknown_manmade_bicycle_case():
    """
    Submerged bicycle case:
    Clearly man-made object with valid shadow and high anomaly contrast,
    but does NOT fit net_debris, wreck, or pipe.
    Must route to unknown_manmade instead of being forced into wrong class.
    """
    res = decide_target(
        cnn_score=0.82,
        shc_score=0.88,
        regularity_score=0.52,
        motion_penalty=0.0,
        persistence_score=0.55,
        shadow_side="correct",
        height_estimate_m=0.9,
        is_sand_ripple=False,
        s_net=0.20,             # NOT a net
        anomaly_score=0.72,     # High anomaly
        dims_px=(24.0, 18.0),   # NOT a massive wreck, NOT an elongated pipe
    )
    assert res.decision == "unknown_manmade"
    assert res.class_name == "unknown_manmade"
    assert res.suppressed is False
    assert "unknown_manmade" in res.decision_reason.lower()
    assert "rejected known classes" in res.decision_reason.lower()
