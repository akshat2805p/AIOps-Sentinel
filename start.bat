@echo off
TITLE AIOps Sentinel Launcher
color 0B

echo ======================================================================
echo                 AIOps Sentinel - Autonomous Telemetry
echo                 Anomaly Detection ^& Incident Risk Platform
echo ======================================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Python environment...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not found in system PATH.
    echo Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

echo [2/3] Checking ML model artifacts...
if not exist "ml\models\isolation_forest.joblib" (
    echo [NOTICE] Trained models not found. Running training pipeline from scratch...
    echo - Step 1: Generating normal baseline telemetry...
    python simulator\generate_normal.py --days 2
    echo - Step 2: Injecting realistic server anomalies...
    python simulator\inject_anomalies.py
    echo - Step 3: Preparing time-series splits and normalization...
    python ml\src\prepare_data.py
    echo - Step 4: Building rolling window temporal features...
    python ml\src\make_windows.py
    echo - Step 5: Training Isolation Forest model...
    python ml\src\train_anomaly.py
    echo [SUCCESS] Model training complete!
) else (
    echo [OK] Trained Isolation Forest model found in ml\models.
)

echo.
echo [3/3] Launching AIOps Sentinel API ^& Web Dashboard...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo Starting server on http://localhost:8080
echo Press Ctrl+C in this terminal to shut down the server.
echo.

start "" http://localhost:8080

python -m uvicorn backend.app:app --host 0.0.0.0 --port 8080 --reload

pause
