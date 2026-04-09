# =============================================================
# start.ps1 — Launch the RAG Chat app locally on Windows
# Usage: .\devops\start.ps1
# =============================================================

$ErrorActionPreference = "Stop"

$Root        = Split-Path $PSScriptRoot -Parent
$BackendDir  = Join-Path $Root "src\backend"
$FrontendDir = Join-Path $Root "src\frontend"
$ReqFile     = Join-Path $Root "requirements.txt"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Azure RAG Chat — Local Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Install dependencies ──────────────────────────────
Write-Host "[1/3] Installing Python dependencies..." -ForegroundColor Yellow
pip install -r $ReqFile --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed."; exit 1 }
Write-Host "  ✅ Dependencies installed." -ForegroundColor Green

# ── Step 2: Start backend ─────────────────────────────────────
Write-Host "[2/3] Starting FastAPI backend (port 50505)..." -ForegroundColor Yellow
$backendJob = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "50505", "--reload" `
    -WorkingDirectory $BackendDir `
    -PassThru `
    -WindowStyle Normal

Write-Host "  ✅ Backend PID: $($backendJob.Id)" -ForegroundColor Green
Start-Sleep -Seconds 3

# ── Step 3: Start frontend ────────────────────────────────────
Write-Host "[3/3] Starting Streamlit frontend (port 8501)..." -ForegroundColor Yellow
$frontendJob = Start-Process -FilePath "python" `
    -ArgumentList "-m", "streamlit", "run", "streamlit_app.py", "--server.port", "8501" `
    -WorkingDirectory $FrontendDir `
    -PassThru `
    -WindowStyle Normal

Write-Host "  ✅ Frontend PID: $($frontendJob.Id)" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Backend  : http://localhost:50505" -ForegroundColor White
Write-Host "  Frontend : http://localhost:8501" -ForegroundColor White
Write-Host "  API Docs : http://localhost:50505/docs" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C or close the terminal windows to stop." -ForegroundColor DarkGray

# Keep script alive so user can Ctrl+C
try {
    while ($true) { Start-Sleep -Seconds 5 }
} finally {
    Write-Host "`nStopping services..." -ForegroundColor Yellow
    Stop-Process -Id $backendJob.Id  -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendJob.Id -ErrorAction SilentlyContinue
    Write-Host "Done." -ForegroundColor Green
}
