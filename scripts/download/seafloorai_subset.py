"""
SeafloorAI Acoustic Habitat Mapping Subset Manager.
Source: Hugging Face (seafloorai)
Licence: CC-BY-NC-SA-4.0
Usage: Seabed roughness calibration and substrate texture modeling.
Strict restriction: Geological substrate maps must NEVER be treated as debris hazard labels.
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("seafloorai_manager")

def manage_seafloorai_subset(data_root: Path = None):
    if data_root is None:
        data_root = Path(__file__).resolve().parents[2] / "data"

    dest_dir = data_root / "raw" / "seafloorai"
    dest_dir.mkdir(parents=True, exist_ok=True)
    license_file = data_root / "licenses" / "seafloorai.txt"

    info = {
        "dataset_name": "SeafloorAI Acoustic Habitat Mapping",
        "source": "https://huggingface.co/datasets/seafloorai",
        "licence": "CC-BY-NC-SA-4.0",
        "intended_use": "Acoustic backscatter calibration and seabed roughness modeling only.",
        "restriction": "Never treat geological sediment labels as debris targets."
    }
    (dest_dir / "dataset_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    if not license_file.exists():
        license_file.write_text("CC-BY-NC-SA-4.0 License\nSeafloorAI Acoustic Habitat Mapping Dataset.\n", encoding="utf-8")

    logger.info("SeafloorAI habitat subset configuration registered under CC-BY-NC-SA-4.0.")
    return True

if __name__ == "__main__":
    manage_seafloorai_subset()
