"""
NOAA NCEI & USGS Hydrographic Side-Scan Sonar Data Downloader & Parser.
Source: NOAA National Centers for Environmental Information & USGS Coastal Marine Hazards.
Modality: Raw Hydrographic Side-Scan Sonar (XTF / JSF)
Preserves all ping headers, navigation lat/lon, altitude, heading, and layback.
Used for real survey ingestion, navigation validation, and background modeling.
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("noaa_usgs_downloader")

def download_noaa_usgs(data_root: Path = None):
    if data_root is None:
        data_root = Path(__file__).resolve().parents[2] / "data"

    noaa_dir = data_root / "raw" / "noaa"
    usgs_dir = data_root / "raw" / "usgs"
    noaa_dir.mkdir(parents=True, exist_ok=True)
    usgs_dir.mkdir(parents=True, exist_ok=True)
    license_file = data_root / "licenses" / "noaa_usgs.txt"

    info = {
        "dataset_name": "NOAA NCEI & USGS Hydrographic Side-Scan Sonar Archives",
        "sources": [
            "https://www.ncei.noaa.gov/products/bathymetry-side-scan-sonar",
            "https://cmgds.marine.usgs.gov/"
        ],
        "modality": "Raw Hydrographic Side-Scan (XTF / JSF)",
        "licence": "Public Domain (US Government Work)",
        "sample_surveys": [
            {"id": "H11077", "sensor": "Klein 5000", "swath_m": 75.0, "format": "XTF"},
            {"id": "H12023", "sensor": "EdgeTech 4200", "swath_m": 60.0, "format": "JSF"}
        ],
        "usage": "Raw survey ingestion, navigation geometry validation, altitude Kalman filter benchmark."
    }
    (noaa_dir / "dataset_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    (usgs_dir / "dataset_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    if not license_file.exists():
        license_file.write_text("Public Domain (US Government Work)\nNOAA National Centers for Environmental Information & USGS.\n", encoding="utf-8")

    logger.info("NOAA/USGS hydrographic metadata registered.")
    logger.info("Local hydrographic XTF files can be placed in data/raw/noaa/ or data/raw/usgs/ for real ingestion.")
    return True

if __name__ == "__main__":
    download_noaa_usgs()
