# TrustShield frontend — Terminal 2
# Usage:  ./run_frontend.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location (Join-Path $root "frontend")
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Write-Host "Installing frontend deps (first run)..." -ForegroundColor Cyan
    npm install --no-audit --no-fund
}
Write-Host "TrustShield UI -> http://localhost:3000" -ForegroundColor Green
npm run dev
