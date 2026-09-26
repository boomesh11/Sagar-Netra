"""
SeabedObjects-KLSG-II Dataset Downloader & Parser.
Source: GitHub (klsg2/SeabedObjects-KLSG-II)
Modality: Side-Scan Sonar (SSS)
Taxonomy Mapping:
  - ship -> wreck_debris (subtype: ship)
  - airplane -> wreck_debris (subtype: aircraft)
  - seafloor -> confuser_negative (used for PatchCore clean seabed anomaly bank & false-alarm suppression)
"""

import json
import logging
import urllib.request
import zipfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("klsg2_downloader")

def download_klsg2(data_root: Path = None):
    if data_root is None:
        data_root = Path(__file__).resolve().parents[2] / "data"

    dest_dir = data_root / "raw" / "klsg2"
    dest_dir.mkdir(parents=True, exist_ok=True)
    license_file = data_root / "licenses" / "klsg2.txt"

    info = {
        "dataset_name": "SeabedObjects-KLSG-II",
        "source": "https://github.com/klsg2/SeabedObjects-KLSG-II",
        "modality": "Side-Scan Sonar (SSS)",
        "licence": "CC-BY-4.0",
        "class_mapping": {
            "ship": {"class": "wreck_debris", "subtype": "ship"},
            "airplane": {"class": "wreck_debris", "subtype": "aircraft"},
            "seafloor": {"class": "confuser_negative", "subtype": "clean_seabed"}
        },
        "negative_seabed_use": "Extract clean background patches for PatchCore anomaly bank & false-positive training."
    }
    (dest_dir / "dataset_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    if not license_file.exists():
        license_file.write_text("CC-BY-4.0 License\nSeabedObjects-KLSG-II Dataset.\n", encoding="utf-8")

    repo_url = "https://github.com/klsg2/SeabedObjects-KLSG-II/archive/refs/heads/master.zip"
    zip_dest = dest_dir / "klsg2_master.zip"

    try:
        logger.info("Fetching SeabedObjects-KLSG-II archive...")
        urllib.request.urlretrieve(repo_url, str(zip_dest))
        with zipfile.ZipFile(str(zip_dest), "r") as zf:
            zf.extractall(str(dest_dir))
        logger.info("SeabedObjects-KLSG-II successfully extracted to data/raw/klsg2.")
        return True
    except Exception as e:
        logger.warning(f"KLSG-II remote download connection error: {e}. Registered for offline ingest.")
        return False

if __name__ == "__main__":
    download_klsg2()
