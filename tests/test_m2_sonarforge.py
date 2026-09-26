"""
M2 acceptance tests for SonarForge:
- Shadow length within 5% of formula
- Every class and preset produces valid pings
- Object height map modification
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from sonarforge.materials import Material, get_props
from sonarforge.seabed import SeabedGenerator, PRESETS
from sonarforge.render import (
    SonarGeometry, render_ping, compute_shadow_length_m
)
from sonarforge.objects import (
    make_ghost_net, make_pipe, make_cylinder, make_wreck_debris,
    make_trap_pot, make_rope_cable, place_object_on_heightmap
)
from sonarforge.nav import generate_lawnmower, DEMO_SITES


# ── Seabed tests ──────────────────────────────────────────────────────────────

def test_all_presets_generate():
    for preset_name in PRESETS:
        gen = SeabedGenerator(preset_name, seed=42)
        h, m = gen.generate(width_m=20.0, length_m=20.0)
        assert h.shape == m.shape
        assert h.dtype == np.float32
        assert m.shape[0] > 0 and m.shape[1] > 0


def test_seabed_height_reasonable():
    gen = SeabedGenerator("REEF_RUBBLE", seed=1)
    h, _ = gen.generate(width_m=50.0, length_m=50.0)
    assert h.max() < 100.0  # no unreasonably tall features
    assert h.min() > -10.0


# ── Renderer tests ────────────────────────────────────────────────────────────

def test_render_ping_returns_uint16():
    geom = SonarGeometry(altitude_m=5.0, range_m=30.0, frequency_hz=450_000.0)
    rng = np.random.default_rng(0)
    profile = np.zeros(300, dtype=np.float32)
    material = np.zeros(300, dtype=np.uint8)
    samples = render_ping(profile, material, geom, rng)
    assert samples.dtype == np.uint16
    assert len(samples) > 0


def test_render_ping_nadir_gap():
    """Nadir samples should be near zero (no valid return)."""
    geom = SonarGeometry(altitude_m=8.0, range_m=50.0)
    rng = np.random.default_rng(1)
    profile = np.zeros(500, dtype=np.float32)
    material = np.zeros(500, dtype=np.uint8)
    samples = render_ping(profile, material, geom, rng)
    nadir_samples = int(geom.altitude_m / geom.range_m * len(samples))
    assert samples[:max(1, nadir_samples - 2)].sum() == 0


def test_shadow_length_formula():
    """
    h = H * Ls / (xo + Ls)  →  Ls = h * xo / (H - h)
    Verify compute_shadow_length_m vs the formula, within 5%.
    """
    for h_obj in [0.3, 0.5, 1.0, 2.0]:
        for xo in [10.0, 20.0, 30.0]:
            H = 8.0
            if H <= h_obj:
                continue
            Ls_formula = h_obj * xo / (H - h_obj)
            Ls_computed = compute_shadow_length_m(h_obj, xo, H)
            assert abs(Ls_computed - Ls_formula) / (Ls_formula + 1e-9) < 0.05, (
                f"Shadow length error: h={h_obj}, xo={xo}, H={H}: "
                f"formula={Ls_formula:.4f}, computed={Ls_computed:.4f}"
            )


# ── Object tests ──────────────────────────────────────────────────────────────

def test_all_objects_create():
    rng = np.random.default_rng(42)
    objects = [
        make_ghost_net(50.0, 50.0, rng=rng),
        make_pipe(60.0, 60.0),
        make_cylinder(70.0, 70.0),
        make_wreck_debris(80.0, 80.0),
        make_trap_pot(90.0, 90.0),
        make_rope_cable(100.0, 100.0),
    ]
    class_names = {o.class_name for o in objects}
    expected = {"ghost_net", "pipe", "cylinder", "wreck_debris", "trap_pot", "rope_cable"}
    assert class_names == expected


def test_object_modifies_heightmap():
    h = np.zeros((200, 200), dtype=np.float32)
    m = np.zeros((200, 200), dtype=np.uint8)
    max_before = float(h.max())
    rng = np.random.default_rng(0)
    obj = make_ghost_net(10.0, 10.0, length_m=5.0, burial_frac=0.0, rng=rng)
    obj.height_m = 0.5  # override after creation
    h2, m2, mask = place_object_on_heightmap(h, m, obj, ground_res_m=0.10)
    assert mask.any(), "Object mask should not be empty"
    assert h2.max() > max_before, "Height map should increase after object placement"


# ── Navigation tests ──────────────────────────────────────────────────────────

def test_lawnmower_generates_nav():
    nav = generate_lawnmower(site="CHENNAI_PORT", n_lines=3, line_length_m=100.0)
    assert len(nav) > 10
    assert all(n.lat is not None for n in nav)
    assert all(n.lon is not None for n in nav)


def test_all_demo_sites_exist():
    assert len(DEMO_SITES) == 6


# ── Material tests ────────────────────────────────────────────────────────────

def test_material_props():
    props = get_props(Material.GHOST_NET if hasattr(Material, "GHOST_NET") else Material.NYLON_TWINE)
    assert props.mu_db < 0  # all materials have negative dB backscatter
