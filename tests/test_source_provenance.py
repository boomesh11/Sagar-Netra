"""
tests/test_source_provenance.py
===============================
Verifies that all targets, evaluation metrics, and dataset sources retain
unbroken provenance (REAL, HYBRID, SIM) and that no synthetic or hybrid performance
is ever represented as real field data.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.sagarnetra.api.app import app

ROOT = Path(__file__).resolve().parent.parent


def test_target_provenance_retention():
    """Verify that every detection in the system carries an explicit source_type."""
    client = TestClient(app)
    resp = client.get("/api/targets")
    assert resp.status_code == 200
    targets = resp.json()["targets"]
    assert len(targets) > 0

    valid_sources = {"REAL", "HYBRID", "SIM"}
    for t in targets:
        assert "source_type" in t, f"Target {t['target_id']} missing source_type"
        assert t["source_type"] in valid_sources, f"Invalid source_type {t['source_type']}"


def test_ghost_net_metrics_provenance_honesty():
    """
    Verify that ghost-net metrics strictly distinguish between:
    - Hybrid benchmark (physics simulated net in real seabed)
    - Real field validation (must be NOT_ESTABLISHED / pending verified field data)
    """
    real_f = ROOT / "artifacts" / "metrics" / "real_metrics.json"
    hybrid_f = ROOT / "artifacts" / "metrics" / "hybrid_metrics.json"

    assert real_f.exists(), "real_metrics.json must exist"
    assert hybrid_f.exists(), "hybrid_metrics.json must exist"

    real_data = json.loads(real_f.read_text(encoding="utf-8"))
    assert real_data["classes"]["ghost_net"]["status"] == "NOT_ESTABLISHED"
    assert "pending verified field data" in real_data["classes"]["ghost_net"]["disclaimer"]

    hybrid_data = json.loads(hybrid_f.read_text(encoding="utf-8"))
    assert hybrid_data["source_type"] == "hybrid"
    assert "ghost_net" in hybrid_data["classes"]


def test_indian_data_provenance_honesty():
    """Verify that Indian field data is never fabricated."""
    client = TestClient(app)
    resp = client.get("/api/datasets/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["indian_field_data"]["status"] == "REAL INDIAN FIELD DATA NOT LOADED"
    assert "Strict refusal to fabricate" in data["indian_field_data"]["policy"]
