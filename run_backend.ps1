# TrustShield backend — Terminal 1
# Usage:  ./run_backend.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Creating venv + installing deps (first run)..." -ForegroundColor Cyan
    py -m venv (Join-Path $root "backend\.venv")
    & $py -m pip install --upgrade pip
    & $py -m pip install -r (Join-Path $root "backend\requirements.txt")
    & $py -m playwright install chromium
}
Set-Location (Join-Path $root "backend")
$env:PYTHONUNBUFFERED = "1"   # stream ts.* pipeline logs live
Write-Host "TrustShield API -> http://127.0.0.1:8000  (docs at /docs)" -ForegroundColor Green
& $py -m uvicorn app.main:app --reload --port 8000
