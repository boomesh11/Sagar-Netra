"""
M1 acceptance tests: data contracts, XTF writer round-trip, SNL round-trip.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from backend.sagarnetra.io.schema import (
    Detection,
    DetectionStatus,
    HazardClass,
    Ping,
    PingFlag,
    Survey,
    DataSource,
)
from backend.sagarnetra.io.xtf_writer import write_xtf
from backend.sagarnetra.io.snl import write_snl, read_snl


# ── Schema tests ──────────────────────────────────────────────────────────────

def test_ping_schema():
    p = Ping(ping_id=0, timestamp_utc=1234567890.0, range_m=50.0)
    assert p.ping_id == 0
    assert p.sound_speed_mps == 1500.0
    assert p.flags == []


def test_ping_with_nav():
    p = Ping(
        ping_id=1,
        timestamp_utc=0.0,
        ship_lat=13.1,
        ship_lon=80.3,
        altitude_m=5.0,
        heading_deg=270.0,
        stbd=list(range(100)),
        port=list(range(100)),
    )
    assert p.ship_lat == pytest.approx(13.1)
    assert len(p.stbd) == 100


def test_survey_schema():
    s = Survey(survey_id="test-001", sensor_model="XTF", frequency_hz=450_000.0)
    assert s.survey_id == "test-001"


def test_detection_schema():
    d = Detection(
        id="det-001",
        cls=HazardClass.GHOST_NET,
        status=DetectionStatus.CANDIDATE,
        hazard_confidence=75.0,
        source=DataSource.HYBRID,
    )
    assert d.cls == HazardClass.GHOST_NET
    assert d.hazard_confidence == 75.0


def test_ping_flag_enum():
    p = Ping(ping_id=0, timestamp_utc=0.0, flags=[PingFlag.DROPOUT])
    assert PingFlag.DROPOUT in p.flags


# ── XTF writer test ───────────────────────────────────────────────────────────

def test_xtf_writer_creates_file():
    pings = [
        Ping(
            ping_id=i,
            timestamp_utc=float(i),
            ship_lat=13.1 + i * 0.001,
            ship_lon=80.3,
            altitude_m=5.0,
            range_m=50.0,
            stbd=list(np.random.randint(0, 65535, 500, dtype=np.uint16)),
            port=list(np.random.randint(0, 65535, 500, dtype=np.uint16)),
        )
        for i in range(5)
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "test.xtf"
        write_xtf(out, pings, frequency_hz=450_000.0)
        assert out.exists()
        assert out.stat().st_size > 1024  # at minimum the file header


# ── SNL round-trip test ───────────────────────────────────────────────────────

def test_snl_roundtrip():
    survey = Survey(
        survey_id="snl-test-001",
        sensor_model="SonarForge",
        frequency_hz=900_000.0,
        range_m=30.0,
    )
    pings_in = [
        Ping(
            ping_id=i,
            timestamp_utc=float(i * 0.1),
            ship_lat=9.1 + i * 0.001,
            ship_lon=79.2,
            altitude_m=4.0,
            range_m=30.0,
            stbd=list(np.random.randint(0, 1000, 300, dtype=np.uint16)),
            port=list(np.random.randint(0, 1000, 300, dtype=np.uint16)),
        )
        for i in range(10)
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        snl_path = Path(tmpdir) / "test.snl.h5"
        write_snl(snl_path, survey, pings_in)
        assert snl_path.exists()

        survey_out, pings_out = read_snl(snl_path)
        assert survey_out.survey_id == "snl-test-001"
        assert len(pings_out) == len(pings_in)
        for p_in, p_out in zip(pings_in, pings_out):
            assert p_in.ping_id == p_out.ping_id
            assert p_in.ship_lat == pytest.approx(p_out.ship_lat, abs=1e-6)
            assert p_in.stbd == p_out.stbd
            assert p_in.port == p_out.port
