# ======================================================================
# AIOps Sentinel - PowerShell Launcher
# ======================================================================

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "        AIOps Sentinel - Autonomous Server Anomaly Detection          " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# 1. Check Python
Write-Host "[1/3] Checking Python environment..." -ForegroundColor Yellow
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[ERROR] Python was not found in PATH. Please install Python 3.10+." -ForegroundColor Red
    exit 1
}

# 2. Check Models
Write-Host "[2/3] Checking ML model artifacts..." -ForegroundColor Yellow
if (-not (Test-Path "ml\models\isolation_forest.joblib")) {
    Write-Host "[NOTICE] Trained model not found. Running training pipeline from scratch..." -ForegroundColor Yellow
    python simulator\generate_normal.py --days 2
    python simulator\inject_anomalies.py
    python ml\src\prepare_data.py
    python ml\src\make_windows.py
    python ml\src\train_anomaly.py
    Write-Host "[SUCCESS] Training pipeline completed!" -ForegroundColor Green
} else {
    Write-Host "[OK] Trained Isolation Forest model verified in ml\models." -ForegroundColor Green
}

# 3. Launch Server & Open Browser
Write-Host ""
Write-Host "[3/3] Starting AIOps Sentinel Backend & Web Dashboard..." -ForegroundColor Yellow

# Clean up port 8080 if previously occupied
$occupied = Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($occupied) {
    Stop-Process -Id $occupied -Force -ErrorAction SilentlyContinue
}

Write-Host "Server running at: http://localhost:8080" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to terminate." -ForegroundColor DarkGray
Write-Host ""

# Launch default browser after 1 second delay
Start-Process "http://localhost:8080"

# Start uvicorn
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8080
