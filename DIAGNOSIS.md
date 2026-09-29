# DIAGNOSIS: SagarNetra UI Upload Failure

## 1. Symptoms
- When a user uploads a side-scan sonar raster image (e.g. `wreck_real.png` or `real_sss_tile_wreck.png`) in the web UI, processing failed with an error banner `Analysis failed (500): Internal Server Error`, or appeared to hang with simulated stepper steps.
- In-browser console logged failed API requests to `/api/analyze` or caught `BackendOfflineError` / 500 responses.
- Even if an image was selected, the Analysis view rendered procedural waterfall noise rather than the uploaded sonar image due to disconnected state between upload dialog and canvas renderer.

## 2. Evidence
- **Backend Log Traceback**:
  ```
  File "D:\SIHPS2\backend\sagarnetra\api\app.py", line 298, in analyze_sonar_survey
    report, json_path, overlay_path = run_pipeline(...)
  File "D:\SIHPS2\scripts\run_pipeline.py", line 265, in run_pipeline
    despeckled_img = enhanced_lee_filter(normalized_img, window_size=7)
  File "D:\SIHPS2\backend\sagarnetra\preprocess\despeckle.py", line 56, in enhanced_lee_filter
    mean_sq = _box_filter_2d(img**2, window_size)
  File "D:\SIHPS2\backend\sagarnetra\preprocess\despeckle.py", line 16, in _box_filter_2d
    return uniform_filter(img.astype(np.float32), size=ksize, mode="reflect")
  File "D:\SIHPS2\.venv\Lib\site-packages\scipy\ndimage\_ni_support.py", line 83, in _get_output
    output = np.zeros(shape, dtype=input.dtype.name)
  numpy._core._exceptions._ArrayMemoryError: Unable to allocate 1.56 MiB for an array with shape (640, 640) and data type float32
  OpenBLAS error: Memory allocation still failed after 10 retries, giving up.
  ```
- Direct reproduction via HTTP POST to `http://127.0.0.1:8000/api/analyze` with `wreck_real.png` returned HTTP 500 and "Internal Server Error" when uvicorn was started without thread environment variables set in the host process environment.
- On Windows with multiple OpenBLAS DLLs (`numpy.libs`, `scipy.libs`, `faiss_cpu.libs`), OpenBLAS fails on memory allocation during thread pool initialization unless `OPENBLAS_NUM_THREADS=1` (and `MKL_NUM_THREADS=1`, `OMP_NUM_THREADS=1`) is exported prior to process launch.
- Frontend called TypeScript heuristics (`checkImageModality` in `@/lib/sonar-detector`) in the browser instead of relying solely on the Python backend (violating Rule R3).
- Frontend stepper (`AnalysisView`) ran hardcoded `setTimeout` animations with simulated log text, completely disconnected from backend execution.

## 3. Root Causes
1. **Host Environment Thread Pool Allocation in OpenBLAS / SciPy**:
   `os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")` inside `app.py` was executed after uvicorn and some native dependencies had already loaded, causing OpenBLAS to exhaust memory allocation retry limits when attempting to initialize 16+ worker threads for array operations.
2. **Dual-Engine Violation**:
   The frontend upload flow invoked client-side TypeScript image modality checks from `lib/sonar-detector.ts` instead of treating Python as the single analysis engine.
3. **Schema & State Mismatches**:
   The response format from `app.py` contained disjoint `targets` and `detections` lists with conflicting property names (`components` vs `evidence`, `hazard_confidence` vs `confidence`), causing `lib/api.ts` to construct malformed detection objects or fail silently.
4. **Hardcoded Fallbacks and Fabrication**:
   Lines 461-527 in `app.py` fabricated a fake wreck target whenever 0 candidates were found, preventing blank images from correctly yielding 0 detections.
5. **Simulated Progress Stepper**:
   The UI rendered a dummy 8-step `setTimeout` animation rather than the real pipeline stages and execution timings returned by the backend.

## 4. Fixes Required
1. Ensure `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1` are exported in `start.ps1`, in `scripts/run_pipeline.py`, and at the very entry point before any numpy/scipy imports.
2. Define a unified, strict Pydantic model in `backend/sagarnetra/api/schemas.py` and exact mirrored TypeScript interfaces in `lib/types/analysis.ts` validated with Zod.
3. Eliminate all TypeScript analysis heuristics (`sonar-detector.ts`, client-side modality checks) from upload and analysis workflows; Next.js must only display backend results.
4. Return real pipeline stage timings and execution metadata in POST `/api/analyze` so the UI stepper renders real execution state.
5. Remove all fabricated fallback targets from `app.py`.
