.PHONY: setup data-synth data-real dataset train train-quick calibrate export evaluate demo test lint typecheck

PYTHON := py -3
PIP    := $(PYTHON) -m pip

# ── Environment ───────────────────────────────────────────────────────────────
setup:
	$(PIP) install -r requirements.txt -q
	@echo "Setup complete."

# ── Data ──────────────────────────────────────────────────────────────────────
data-synth:
	$(PYTHON) training/build_dataset.py --mode synth

data-real:
	$(PYTHON) scripts/download/ghostpot.py
	$(PYTHON) scripts/download/sctd.py
	$(PYTHON) scripts/download/sctd2.py
	$(PYTHON) scripts/download/klsg2.py
	$(PYTHON) scripts/download/ai4shipwrecks.py
	$(PYTHON) scripts/download/noaa_usgs_sss.py

dataset:
	$(PYTHON) training/build_dataset.py --mode full

# ── Training ──────────────────────────────────────────────────────────────────
train-quick:
	$(PYTHON) training/train_yolo.py --quick
	$(PYTHON) training/train_anomaly.py
	$(PYTHON) training/calibrate.py
	$(PYTHON) training/export_onnx.py

train:
	$(PYTHON) training/train_yolo.py
	$(PYTHON) training/train_anomaly.py
	$(PYTHON) training/calibrate.py
	$(PYTHON) training/export_onnx.py

calibrate:
	$(PYTHON) training/calibrate.py

export:
	$(PYTHON) training/export_onnx.py

evaluate:
	$(PYTHON) training/evaluate.py
	$(PYTHON) training/ablation.py

# ── Demo ──────────────────────────────────────────────────────────────────────
demo:
	$(PYTHON) sonarforge/scenes.py --generate-demo-logs
	$(PYTHON) -m uvicorn backend.sagarnetra.api.main:app --host 0.0.0.0 --port 8000 &
	@echo "Backend started on http://localhost:8000"
	@echo "Start frontend with: cd frontend && npm run dev"

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check backend/ sonarforge/ training/ scripts/ tests/

typecheck:
	$(PYTHON) -m mypy backend/ sonarforge/ training/
