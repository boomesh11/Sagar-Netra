# scripts/verify_all.ps1
# ======================
# Comprehensive SagarNetra End-to-End Verification Script
# Runs:
# 1. Pytest suite
# 2. 12-Case Fixture Verification Table
# 3. Next.js Frontend Production Build Check

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "SagarNetra End-to-End System Verification (Phases 1-5)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Step 1: Run Pytest
Write-Host "`n[1/3] Running Python pytest test suite..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe -m pytest tests/ -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] Pytest failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "[+] All Pytest tests PASSED!" -ForegroundColor Green

# Step 2: Run Fixture Audit
Write-Host "`n[2/3] Running 12-case acoustic fixture verification..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe audit\run_fixtures_audit.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] Fixture audit failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "[+] Fixture verification completed successfully!" -ForegroundColor Green

# Step 3: Run Frontend Production Build Check
Write-Host "`n[3/3] Checking Next.js production build..." -ForegroundColor Yellow
& npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] Frontend build failed!" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "[+] Frontend build verified clean!" -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "ALL VERIFICATION CHECKS PASSED (100% SUCCESS)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
