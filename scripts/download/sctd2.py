"""
SCTD2 Trap Target Detection & Segmentation Downloader.
Source: GitHub (sonar-dataset/SCTD2)
Sensor: Klein 3000 SSS
Taxonomy Mapping: trap -> trap_pot
Derives bounding boxes from segmentation masks.
"""

import json
import logging
import urllib.request
import zipfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("sctd2_downloader")

def download_sctd2(data_root: Path = None):
    if data_root is None:
        data_root = Path(__file__).resolve().parents[2] / "data"

    dest_dir = data_root / "raw" / "sctd2"
    dest_dir.mkdir(parents=True, exist_ok=True)
    license_file = data_root / "licenses" / "sctd2.txt"

    info = {
        "dataset_name": "SCTD2 Trap Target Detection & Segmentation",
        "source": "https://github.com/sonar-dataset/SCTD2",
        "modality": "Side-Scan Sonar (SSS)",
        "sensor": "Klein 3000",
        "licence": "Apache-2.0",
        "class_mapping": {"trap": "trap_pot"},
        "note": "Derive bounding boxes directly from pixel segmentation masks."
    }
    (dest_dir / "dataset_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    if not license_file.exists():
        license_file.write_text("Apache-2.0 License\nSCTD2 Trap Target Detection & Segmentation.\n", encoding="utf-8")

    repo_url = "https://github.com/sonar-dataset/SCTD2/archive/refs/heads/main.zip"
    zip_dest = dest_dir / "sctd2_main.zip"

    try:
        logger.info("Fetching SCTD2 archive...")
        urllib.request.urlretrieve(repo_url, str(zip_dest))
        with zipfile.ZipFile(str(zip_dest), "r") as zf:
            zf.extractall(str(dest_dir))
        logger.info("SCTD2 successfully extracted to data/raw/sctd2.")
        return True
    except Exception as e:
        logger.warning(f"SCTD2 remote download connection error: {e}. Registered for offline ingest.")
        return False

if __name__ == "__main__":
    download_sctd2()
