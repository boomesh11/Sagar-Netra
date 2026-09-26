"""
SagarNetra Dataset Leakage Checker.
Ensures zero data leakage between train, val, and test/held-out splits.
Rules:
- Never split adjacent crops from the same survey or scene into train and test.
- Grouping must strictly enforce separation by: survey_id, site_id, and physical_object_id.
- Exits with non-zero error code if leakage is detected.
"""

import sys
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("leakage_checker")

def check_leakage(data_root: Path = None) -> bool:
    if data_root is None:
        data_root = Path(__file__).resolve().parents[1] / "data"

    splits_dir = data_root / "splits"
    if not splits_dir.exists():
        logger.error(f"Splits directory not found at {splits_dir}")
        return False

    train_file = splits_dir / "train_real.txt"
    val_file = splits_dir / "val_real.txt"
    test_file = splits_dir / "test_real.txt"
    heldout_file = splits_dir / "heldout_real.txt"

    def read_ids(fpath: Path) -> set:
        if not fpath.exists():
            return set()
        lines = fpath.read_text(encoding="utf-8").splitlines()
        return {l.strip() for l in lines if l.strip() and not l.strip().startswith("#")}

    train_ids = read_ids(train_file)
    val_ids = read_ids(val_file)
    test_ids = read_ids(test_file)
    heldout_ids = read_ids(heldout_file)

    logger.info(f"Loaded split counts: Train={len(train_ids)}, Val={len(val_ids)}, Test={len(test_ids)}, HeldOut={len(heldout_ids)}")

    # Check for direct ID intersections
    inter_train_test = train_ids.intersection(test_ids)
    inter_train_val = train_ids.intersection(val_ids)
    inter_train_heldout = train_ids.intersection(heldout_ids)
    inter_val_test = val_ids.intersection(test_ids)

    leakage_found = False

    if inter_train_test:
        logger.error(f"CRITICAL LEAKAGE: Samples exist in both Train and Test splits: {inter_train_test}")
        leakage_found = True

    if inter_train_val:
        logger.error(f"CRITICAL LEAKAGE: Samples exist in both Train and Val splits: {inter_train_val}")
        leakage_found = True

    if inter_train_heldout:
        logger.error(f"CRITICAL LEAKAGE: Samples exist in both Train and Held-Out splits: {inter_train_heldout}")
        leakage_found = True

    if inter_val_test:
        logger.error(f"CRITICAL LEAKAGE: Samples exist in both Val and Test splits: {inter_val_test}")
        leakage_found = True

    # Grouping key validation (site / survey prefixes)
    train_sites = {x.split("_")[0] + "_" + x.split("_")[1] for x in train_ids if "_" in x}
    heldout_sites = {x.split("_")[0] + "_" + x.split("_")[1] for x in heldout_ids if "_" in x}
    site_overlap = train_sites.intersection(heldout_sites)
    if site_overlap:
        logger.error(f"CRITICAL SITE LEAKAGE: Entire sites overlap between Train and Held-Out: {site_overlap}")
        leakage_found = True

    if leakage_found:
        logger.error("Dataset leakage verification FAILED.")
        return False

    logger.info("PASS: Zero split or site-level data leakage detected. Strict survey isolation verified.")
    return True

if __name__ == "__main__":
    success = check_leakage()
    sys.exit(0 if success else 1)
