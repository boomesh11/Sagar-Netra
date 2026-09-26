"""M0 acceptance test: verify repo structure exists."""
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent

REQUIRED_DIRS = [
    "backend/sagarnetra/io",
    "backend/sagarnetra/preprocess",
    "backend/sagarnetra/detect",
    "backend/sagarnetra/verify",
    "backend/sagarnetra/confidence",
    "backend/sagarnetra/geo",
    "backend/sagarnetra/track",
    "backend/sagarnetra/coverage",
    "backend/sagarnetra/change",
    "backend/sagarnetra/report",
    "backend/sagarnetra/api",
    "sonarforge",
    "training",
    "scripts/download",
    "data/raw",
    "data/licenses",
    "artifacts/metrics",
    "artifacts/models",
    "artifacts/pod",
    "docs",
    "tests",
]

REQUIRED_FILES = [
    "Makefile",
    "pyproject.toml",
    "requirements.txt",
    "docker-compose.yml",
    ".gitignore",
    "docs/PROGRESS.md",
    ".github/workflows/ci.yml",
]


def test_required_directories_exist():
    for d in REQUIRED_DIRS:
        path = ROOT / d
        assert path.exists() and path.is_dir(), f"Missing directory: {d}"


def test_required_files_exist():
    for f in REQUIRED_FILES:
        path = ROOT / f
        assert path.exists() and path.is_file(), f"Missing file: {f}"


def test_python_packages_have_init():
    packages = [
        "backend",
        "backend/sagarnetra",
        "sonarforge",
        "training",
        "tests",
    ]
    for pkg in packages:
        init = ROOT / pkg / "__init__.py"
        assert init.exists(), f"Missing __init__.py in {pkg}"
