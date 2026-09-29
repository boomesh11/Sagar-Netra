"""
SagarNetra - Backend Server Entrypoint
Starts the FastAPI backend server on http://localhost:8000.
Ensures correct sys.path, thread limits, and CORS configuration.
"""
import os
import sys
from pathlib import Path

# Threading optimizations for constrained / CPU environments
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# Add repository root to Python path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import uvicorn

if __name__ == "__main__":
    print(f"[*] SagarNetra Backend initializing from {ROOT_DIR}...")
    print(f"[*] Starting API server on http://127.0.0.1:8000 (docs at /docs)")
    uvicorn.run("backend.sagarnetra.api.app:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
