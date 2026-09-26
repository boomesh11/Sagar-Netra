"""
SCTD 1.0 (Side-scan Sonar Target Detection) Downloader & Parser.
Source: GitHub (Y-Rong/SCTD)
Taxonomy Mapping: ship -> wreck_debris (subtype: ship), airplane -> wreck_debris (subtype: aircraft)
Annotations: Pascal VOC XML
"""

import os
import json
import logging
import urllib.request
import zipfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("sctd_downloader")

def download_sctd(data_root: Path = None):
    if data_root is None:
        data_root = Path(__file__).resolve().parents[2] / "data"

    dest_dir = data_root / "raw" / "sctd"
    dest_dir.mkdir(parents=True, exist_ok=True)
    license_file = data_root / "licenses" / "sctd.txt"

    info = {
        "dataset_name": "SCTD 1.0 Side-scan Sonar Target Detection",
        "source": "https://github.com/Y-Rong/SCTD",
        "modality": "Side-Scan Sonar (SSS)",
        "licence": "MIT",
        "class_mapping": {
            "ship": {"class": "wreck_debris", "subtype": "ship"},
            "airplane": {"class": "wreck_debris", "subtype": "aircraft"}
        }
    }
    (dest_dir / "dataset_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    if not license_file.exists():
        license_file.write_text("MIT License\nSide-scan Sonar Target Detection (SCTD 1.0) by Y-Rong et al.\n", encoding="utf-8")

    logger.info("Initializing SCTD 1.0 download...")
    # GitHub repository zip URL
    repo_url = "https://github.com/Y-Rong/SCTD/archive/refs/heads/master.zip"
    zip_dest = dest_dir / "sctd_master.zip"

    try:
        urllib.request.urlretrieve(repo_url, str(zip_dest))
        logger.info("Extracting SCTD archive...")
        with zipfile.ZipFile(str(zip_dest), "r") as zf:
            zf.extractall(str(dest_dir))
        logger.info("SCTD 1.0 successfully extracted to data/raw/sctd.")
        return True
    except Exception as e:
        logger.warning(f"SCTD remote download connection error: {e}. Dataset info registered for offline ingest.")
        return False

if __name__ == "__main__":
    download_sctd()
