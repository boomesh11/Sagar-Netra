# SagarNetra Unified Launch Script for Windows PowerShell
# Starts Python FastAPI backend (:8000) and Next.js frontend (:3000)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SAGARNETRA: AI-Powered Marine Debris Detection System     " -ForegroundColor Cyan
Write-Host "  National Institute of Ocean Technology (NIOT) / MoES       " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$WorkspaceRoot = $PSScriptRoot
Set-Location $WorkspaceRoot

# Check Python environment
$PythonExe = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "[!] Virtual environment not found at .venv. Please create it or install requirements." -ForegroundColor Red
    exit 1
}

$env:PYTHONPATH = $WorkspaceRoot
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
$env:OPENBLAS_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
$env:NUMEXPR_NUM_THREADS = "1"

Write-Host "[1/2] Launching Python FastAPI Backend (:8000)..." -ForegroundColor Green
$BackendProc = Start-Process -FilePath $PythonExe `
    -ArgumentList "run_backend.py" `
    -PassThru

Write-Host "[*] Backend running with PID $($BackendProc.Id)" -ForegroundColor Gray
Start-Sleep -Seconds 2

# Check if Backend is responding
try {
    $Health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get -TimeoutSec 5
    Write-Host "[+] Backend healthy! Status: $($Health.status)" -ForegroundColor Green
} catch {
    Write-Host "[!] Waiting for backend to finish initialising..." -ForegroundColor Yellow
}

Write-Host "[2/2] Launching Next.js UI Frontend (:3000)..." -ForegroundColor Green
$FrontendProc = Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "dev" `
    -PassThru

Write-Host "[*] Frontend running with PID $($FrontendProc.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  System is LIVE:                                           " -ForegroundColor Cyan
Write-Host "  - UI:      http://localhost:3000                          " -ForegroundColor Yellow
Write-Host "  - API:     http://localhost:8000                          " -ForegroundColor Yellow
Write-Host "  - API Doc: http://localhost:8000/docs                     " -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Press Ctrl+C or close this terminal to stop both services."

# Monitor and cleanup on exit
try {
    while (-not $BackendProc.HasExited -and -not $FrontendProc.HasExited) {
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host "`nStopping SagarNetra processes..." -ForegroundColor Yellow
    if (-not $BackendProc.HasExited) { Stop-Process -Id $BackendProc.Id -Force -ErrorAction SilentlyContinue }
    if (-not $FrontendProc.HasExited) { Stop-Process -Id $FrontendProc.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "All processes stopped cleanly." -ForegroundColor Gray
}
