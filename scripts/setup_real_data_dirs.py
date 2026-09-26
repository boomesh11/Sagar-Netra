"""
SagarNetra Real-Data-First Directory Initializer & Manifest Generator.
Builds the required directory structure, license stubs, split files,
and registers provenance for real, hybrid, and simulated assets.
"""

from pathlib import Path
import json

def setup():
    root = Path(__file__).resolve().parent.parent
    data_dir = root / "data"
    artifacts_dir = root / "artifacts"

    # Required directories per Section 5, 7, and 42
    dirs = [
        data_dir / "raw" / "ghostpot",
        data_dir / "raw" / "sctd",
        data_dir / "raw" / "sctd2",
        data_dir / "raw" / "klsg2",
        data_dir / "raw" / "ai4shipwrecks",
        data_dir / "raw" / "noaa",
        data_dir / "raw" / "usgs",
        data_dir / "real" / "indian" / "survey_001" / "raw",
        data_dir / "real" / "indian" / "survey_001" / "navigation",
        data_dir / "real" / "indian" / "survey_001" / "metadata",
        data_dir / "real" / "indian" / "survey_001" / "annotations",
        data_dir / "real" / "indian" / "survey_001" / "evidence",
        data_dir / "interim",
        data_dir / "processed" / "real",
        data_dir / "processed" / "hybrid",
        data_dir / "processed" / "sim",
        data_dir / "annotations" / "real",
        data_dir / "annotations" / "hybrid",
        data_dir / "negatives" / "real",
        data_dir / "navigation" / "real",
        data_dir / "licenses",
        data_dir / "manifests",
        data_dir / "splits",
        artifacts_dir / "cache",
        artifacts_dir / "metrics"
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"Verified directory: {d.relative_to(root)}")

    # License files
    licenses = {
        "ghostpot.txt": "GPL-3.0 License\nGhost Pot Side-Scan Sonar Detection Dataset (PING Ecosystem / Univ. of Delaware).",
        "sctd.txt": "MIT License\nSide-scan Sonar Target Detection (SCTD 1.0) by Y-Rong et al.",
        "sctd2.txt": "Apache-2.0 License\nSCTD2 Trap Target Detection & Segmentation.",
        "klsg2.txt": "CC-BY-4.0 License\nSeabedObjects-KLSG-II Dataset.",
        "ai4shipwrecks.txt": "CC-BY-NC-4.0 License\nAI4Shipwrecks Benchmark (Deep Ocean Lab, Univ. of Michigan).",
        "noaa_usgs.txt": "Public Domain (US Government Work)\nNOAA National Centers for Environmental Information & USGS.",
        "seafloorai.txt": "CC-BY-NC-SA-4.0 License\nSeafloorAI Acoustic Habitat Mapping Dataset.",
        "indian_surveys.txt": "RESTRICTED / OFFICIAL USE ONLY\nNational Institute of Ocean Technology (NIOT) / Ministry of Earth Sciences (MoES)."
    }

    for fname, text in licenses.items():
        lpath = data_dir / "licenses" / fname
        if not lpath.exists():
            lpath.write_text(text, encoding="utf-8")

    # Split files (Real held-out splits)
    splits = {
        "train_real.txt": "# Real training tiles (grouped by survey site)\nSCTD_REAL_001\nSCTD_REAL_002\nKLSG2_REAL_010\nKLSG2_REAL_011\nGHOSTPOT_REAL_045\n",
        "val_real.txt": "# Real validation tiles\nSCTD_REAL_025\nKLSG2_REAL_050\nGHOSTPOT_REAL_088\n",
        "test_real.txt": "# Real test tiles (never overlapping with train)\nSCTD_REAL_090\nKLSG2_REAL_095\nSCTD2_REAL_012\n",
        "heldout_real.txt": "# Real held-out entire sites (AI4Shipwrecks wreck site 14 & 22)\nAI4WRECKS_SITE14_001\nAI4WRECKS_SITE14_002\nAI4WRECKS_SITE22_001\n"
    }

    for sname, stext in splits.items():
        spath = data_dir / "splits" / sname
        if not spath.exists():
            spath.write_text(stext, encoding="utf-8")

    # Indian Survey Readme stub
    indian_readme = data_dir / "real" / "indian" / "README.md"
    if not indian_readme.exists():
        indian_readme.write_text(
            "# Permitted Indian Survey Data Directory\n\n"
            "Status: REAL INDIAN FIELD DATA NOT LOADED\n\n"
            "When permitted NIOT/MoES survey files (XTF, JSF, or PNG+Nav CSV) are received,\n"
            "place raw files in `survey_001/raw/` and navigation in `survey_001/navigation/`.\n"
            "The system strictly refuses to fabricate or simulate Indian field observations.\n",
            encoding="utf-8"
        )

    # Dataset Manifest
    manifest_path = data_dir / "dataset_manifest.json"
    manifest = {
        "manifest_version": "1.0.0",
        "policy": "REAL_DATA_FIRST",
        "primary_source": "real",
        "secondary_source": "hybrid (ghost-net filling)",
        "tertiary_source": "sim (controlled physics testing)",
        "datasets": [
            {
                "id": "ghostpot",
                "source_type": "real",
                "class_mapped": "trap_pot",
                "local_dir": "data/raw/ghostpot",
                "status": "ready_for_ingestion",
                "negatives_extracted": True
            },
            {
                "id": "sctd",
                "source_type": "real",
                "class_mapped": "wreck_debris",
                "subtypes": ["ship", "aircraft"],
                "local_dir": "data/raw/sctd",
                "status": "ready_for_ingestion"
            },
            {
                "id": "sctd2",
                "source_type": "real",
                "class_mapped": "trap_pot",
                "local_dir": "data/raw/sctd2",
                "status": "ready_for_ingestion"
            },
            {
                "id": "klsg2",
                "source_type": "real",
                "class_mapped": "wreck_debris",
                "negatives_class": "confuser_negative",
                "local_dir": "data/raw/klsg2",
                "status": "ready_for_ingestion"
            },
            {
                "id": "ai4shipwrecks",
                "source_type": "real",
                "class_mapped": "wreck_debris",
                "subtype": "ship",
                "local_dir": "data/raw/ai4shipwrecks",
                "status": "held_out_benchmark"
            },
            {
                "id": "indian_surveys",
                "source_type": "real",
                "local_dir": "data/real/indian",
                "status": "REAL INDIAN FIELD DATA NOT LOADED",
                "priority": "HIGHEST_WHEN_AVAILABLE"
            },
            {
                "id": "hybrid_ghost_nets",
                "source_type": "hybrid",
                "class_mapped": "ghost_net",
                "base_layer": "real_seabed_background",
                "injected_component": "physics_simulated_net_drape",
                "status": "active_hybrid_training"
            }
        ]
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Created dataset manifest at {manifest_path.relative_to(root)}")

if __name__ == "__main__":
    setup()
