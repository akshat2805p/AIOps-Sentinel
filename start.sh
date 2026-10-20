#!/usr/bin/env bash
set -e

echo "======================================================================"
echo "                AIOps Sentinel - Autonomous Telemetry                 "
echo "                Anomaly Detection & Incident Risk Platform            "
echo "======================================================================"
echo ""

cd "$(dirname "$0")"

echo "[1/3] Checking Python environment..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 is not installed or not in PATH."
    exit 1
fi

echo "[2/3] Checking ML model artifacts..."
if [ ! -f "ml/models/isolation_forest.joblib" ]; then
    echo "[NOTICE] Model not found. Training model pipeline from scratch..."
    python3 simulator/generate_normal.py --days 2
    python3 simulator/inject_anomalies.py
    python3 ml/src/prepare_data.py
    python3 ml/src/make_windows.py
    python3 ml/src/train_anomaly.py
    echo "[SUCCESS] Training pipeline completed!"
else
    echo "[OK] Model artifacts verified."
fi

echo ""
echo "[3/3] Starting AIOps Sentinel Backend & Web Dashboard on http://localhost:8080 ..."
python3 -m uvicorn backend.app:app --host 0.0.0.0 --port 8080
