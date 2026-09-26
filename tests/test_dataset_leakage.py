"""
tests/test_dataset_leakage.py
=============================
Verifies zero data leakage between training and evaluation splits:
- No survey line or physical site overlap between train_real and test_real / heldout_real
- Enforces strict site/survey grouping key
"""

from pathlib import Path
import pytest
from scripts.check_leakage import check_leakage

ROOT = Path(__file__).resolve().parent.parent


def test_no_site_or_survey_leakage():
    """Verify that train_real and test_real / heldout_real have zero overlapping survey sites."""
    is_clean = check_leakage()
    assert is_clean is True, "Data leakage detected between train and test/heldout splits"


def test_split_files_non_empty():
    """Verify all split files exist and contain valid entries."""
    splits_dir = ROOT / "data" / "splits"
    for split_name in ["train_real.txt", "val_real.txt", "test_real.txt", "heldout_real.txt"]:
        f = splits_dir / split_name
        assert f.exists(), f"Split file {split_name} missing"
        lines = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) > 0, f"Split file {split_name} is empty"
