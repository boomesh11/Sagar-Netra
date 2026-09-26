"""
Ghost Pot Side-Scan Sonar Dataset Downloader & Parser.
Source: Hugging Face (PING-ecosystem/ghostpot)
Sensor: Humminbird Side-Scan Sonar
Taxonomy Mapping: crab_pot -> trap_pot
Usage: Extract real trap/pot targets and clean seabed background negative tiles.
"""

import os
import sys
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("ghostpot_downloader")

def download_ghostpot(data_root: Path = None):
    if data_root is None:
        data_root = Path(__file__).resolve().parents[2] / "data"

    dest_dir = data_root / "raw" / "ghostpot"
    dest_dir.mkdir(parents=True, exist_ok=True)
    license_file = data_root / "licenses" / "ghostpot.txt"

    logger.info("Checking Ghost Pot dataset access...")
    hf_token = os.environ.get("HF_TOKEN")
    
    # Write metadata description
    info = {
        "dataset_name": "Ghost Pot Side-Scan Sonar Detection Dataset",
        "source": "https://huggingface.co/datasets/PING-ecosystem/ghostpot",
        "modality": "Side-Scan Sonar (SSS)",
        "sensor": "Humminbird Side-Scan",
        "licence": "GPL-3.0",
        "mapping": {"crab_pot": "trap_pot", "maybe_crab_pot": "trap_pot"},
        "note": "Crab pots are mapped as trap_pot, NEVER as ghost_net. Real seabed tiles used as negative background."
    }
    (dest_dir / "dataset_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    if not license_file.exists():
        license_file.write_text("GPL-3.0 License\nGhost Pot Side-Scan Sonar Detection Dataset (PING Ecosystem / Univ. of Delaware).\n", encoding="utf-8")

    if not hf_token:
        logger.warning("HF_TOKEN environment variable not set. Ghost Pot is a gated dataset.")
        logger.info("To download full weights, set HF_TOKEN=<token> and re-run. Offline placeholder metadata initialized.")
        return False

    logger.info("HF_TOKEN detected. Initializing gated Hugging Face download...")
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id="PING-ecosystem/ghostpot",
            repo_type="dataset",
            local_dir=str(dest_dir),
            token=hf_token,
            max_workers=4
        )
        logger.info("Successfully fetched Ghost Pot dataset files.")
        return True
    except Exception as e:
        logger.error(f"Download failed: {e}. Ensure HF_TOKEN has granted permissions.")
        return False

if __name__ == "__main__":
    download_ghostpot()
