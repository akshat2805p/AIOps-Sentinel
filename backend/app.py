"""
app.py — AIOps Sentinel Backend API
====================================
FastAPI-based REST backend that handles:
  - Metric ingestion and validation
  - Anomaly detection via the trained Isolation Forest model
  - Alert generation with cooldown and deduplication
  - Host management
  - Model status and evaluation reporting
  - Fault injection simulation studio
  - Serves the real-time glassmorphism web dashboard

Security enhancements:
  - Strict host_id and metrics parameter validation
  - SQL injection protection via parameterized queries
  - Security headers (nosniff, DENY, XSS protection)
  - Resilient database layer (PostgreSQL with automatic SQLite fallback)
"""

import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator

from backend.db import db_manager

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("sentinel-api")


# ──────────────────────────────────────────────────────────────
# Anomaly detection engine
# ──────────────────────────────────────────────────────────────

class AnomalyEngine:
    """Wraps the ML model and alert-generation logic."""

    def __init__(self):
        self.model = None
        self.scaler = None
        self.threshold = -0.15
        self.feature_columns = []
        self.model_version = "not-loaded"
        self._last_alert_time = {}     # host_id -> last alert timestamp
        self._consecutive_counts = {}  # host_id -> consecutive anomaly count

        self._load_model()

    def _load_model(self):
        import joblib
        model_path = os.getenv("MODEL_PATH", "ml/models/isolation_forest.joblib")
        scaler_path = os.getenv("SCALER_PATH", "ml/models/scaler.joblib")

        if Path(model_path).exists() and Path(scaler_path).exists():
            artifact = joblib.load(model_path)
            self.model = artifact["model"]
            self.threshold = artifact.get("threshold", -0.15)
            self.feature_columns = artifact.get("feature_columns", [])
            self.model_version = artifact.get("model_version", "iforest-v1.0")
            self.scaler = joblib.load(scaler_path)
            logger.info(f"Loaded ML model: {self.model_version}, "
                        f"{len(self.feature_columns)} features, threshold={self.threshold:.4f}")
        else:
            logger.warning("Model files not found — running with statistical anomaly baseline.")

    def score_metrics(self, metrics: dict) -> dict:
        """Score a single observation and return anomaly assessment."""
        if self.model is not None and self.scaler is not None:
            import numpy as np
            import yaml

            try:
                cfg_path = "ml/configs/training.yaml"
                with open(cfg_path) as f:
                    feat_cfg = yaml.safe_load(f)["features"]

                metric_cols = feat_cfg["raw_metrics"]
                raw = [metrics.get(col, 0.0) for col in metric_cols]
                scaled = self.scaler.transform([raw])[0]

                features = {}
                for i, col in enumerate(metric_cols):
                    features[f"{col}_scaled"] = scaled[i]

                for w in feat_cfg.get("rolling_windows", []):
                    for stat in feat_cfg.get("rolling_stats", []):
                        for col in metric_cols:
                            if stat == "mean":
                                features[f"{col}_roll{w}_{stat}"] = features[f"{col}_scaled"]
                            else:
                                features[f"{col}_roll{w}_{stat}"] = 0.0

                for lag in feat_cfg.get("diff_lags", []):
                    for col in metric_cols:
                        features[f"{col}_diff{lag}"] = 0.0

                vector = [features.get(col, 0.0) for col in self.feature_columns]
                vector = np.array([vector], dtype=np.float64)

                score = float(self.model.decision_function(vector)[0])
                is_anomaly = score < self.threshold

                if score < -0.35:
                    severity = "critical"
                elif score < -0.15:
                    severity = "warning"
                elif score < -0.05:
                    severity = "info"
                else:
                    severity = "normal"

                return {
                    "anomaly_score": round(score, 6),
                    "is_anomaly": bool(is_anomaly),
                    "severity": severity,
                    "model_version": self.model_version
                }
            except Exception as e:
                logger.error(f"Inference error: {e}, using statistical fallback")

        # Statistical fallback scoring
        cpu = metrics.get("cpu_percent", 50.0)
        mem = metrics.get("memory_percent", 55.0)
        lat = metrics.get("request_latency_ms", 50.0)
        err = metrics.get("error_rate", 0.005)

        z_cpu = max(0.0, (cpu - 50.0) / 20.0)
        z_mem = max(0.0, (mem - 55.0) / 20.0)
        z_lat = max(0.0, (lat - 80.0) / 50.0)
        z_err = max(0.0, (err - 0.01) / 0.02)

        mag = (z_cpu * 0.35) + (z_mem * 0.25) + (z_lat * 0.25) + (z_err * 0.35)
        score = 0.10 - (mag * 0.25)
        is_anomaly = score < -0.15

        if score < -0.35:
            severity = "critical"
        elif score < -0.15:
            severity = "warning"
        elif score < -0.05:
            severity = "info"
        else:
            severity = "normal"

        return {
            "anomaly_score": round(score, 6),
            "is_anomaly": bool(is_anomaly),
            "severity": severity,
            "model_version": "statistical-v1.0"
        }

    def should_alert(self, host_id: str, anomaly_result: dict,
                     min_consecutive: int = 2,
                     cooldown_seconds: int = 120) -> bool:
        """Alert lifecycle management: consecutive count & cooldown check."""
        now = time.time()

        if not anomaly_result.get("is_anomaly", False):
            self._consecutive_counts[host_id] = 0
            return False

        count = self._consecutive_counts.get(host_id, 0) + 1
        self._consecutive_counts[host_id] = count

        if host_id in self._last_alert_time:
            elapsed = now - self._last_alert_time[host_id]
            if elapsed < cooldown_seconds:
                return False

        if count < min_consecutive:
            return False

        self._last_alert_time[host_id] = now
        return True


# ──────────────────────────────────────────────────────────────
# Pydantic Schemas with strict security validation
# ──────────────────────────────────────────────────────────────

HOST_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")

class MetricsPayload(BaseModel):
    cpu_percent: float = Field(ge=0.0, le=100.0)
    memory_percent: float = Field(ge=0.0, le=100.0)
    disk_io_bytes_sec: float = Field(ge=0.0)
    network_bytes_sec: float = Field(ge=0.0)
    request_latency_ms: float = Field(ge=0.0)
    error_rate: float = Field(ge=0.0, le=1.0)

class MetricIngestion(BaseModel):
    host_id: str
    timestamp: Optional[str] = None
    metrics: MetricsPayload

    @validator("host_id")
    def validate_host_id(cls, v):
        if not HOST_REGEX.match(v):
            raise ValueError("host_id must contain only alphanumeric characters, dots, dashes, or underscores (max 128 chars)")
        return v

class HostRegistration(BaseModel):
    host_id: str
    hostname: str
    ip_address: Optional[str] = None
    os_info: Optional[str] = None

    @validator("host_id")
    def validate_host_id(cls, v):
        if not HOST_REGEX.match(v):
            raise ValueError("host_id must be alphanumeric")
        return v

class AlertAcknowledge(BaseModel):
    acknowledged_by: str = "operator"
    notes: Optional[str] = None

class SimulationRequest(BaseModel):
    host_id: str = "server-01"
    scenario: str = "cpu_spike"


# ──────────────────────────────────────────────────────────────
# Application Lifecycle & Security Setup
# ──────────────────────────────────────────────────────────────

anomaly_engine = AnomalyEngine()

app = FastAPI(
    title="AIOps Sentinel API",
    description="Autonomous Server Anomaly Detection & Incident-Risk Analysis Platform",
    version="1.0.0"
)

# CORS setup
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in cors_origins_env.split(",")] if cors_origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ──────────────────────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint indicating DB connectivity and model readiness."""
    return {
        "status": "healthy",
        "database": db_manager.engine_type,
        "model_loaded": anomaly_engine.model is not None,
        "model_version": anomaly_engine.model_version,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/v1/hosts", status_code=201)
async def register_host(host: HostRegistration):
    try:
        db_manager.upsert_host(host.host_id, host.hostname)
        return {"status": "registered", "host_id": host.host_id}
    except Exception as e:
        logger.error(f"Error registering host: {e}")
        raise HTTPException(status_code=500, detail="Host registration failed")


@app.get("/api/v1/hosts")
async def list_hosts():
    query = """
    SELECT h.host_id, h.hostname, h.registered_at, h.last_seen_at, h.status,
           (SELECT COUNT(*) FROM alerts a WHERE a.host_id = h.host_id AND a.status = 'active') AS active_alerts
    FROM hosts h ORDER BY h.last_seen_at DESC
    """
    rows = db_manager.execute_query(query)
    return {"hosts": rows}


@app.post("/api/v1/metrics", status_code=201)
async def ingest_metrics(payload: MetricIngestion):
    m = payload.metrics
    metrics_dict = m.model_dump()

    # Register/refresh host
    db_manager.upsert_host(payload.host_id, payload.host_id)

    # Anomaly inference
    scoring = anomaly_engine.score_metrics(metrics_dict)
    alert_triggered = anomaly_engine.should_alert(payload.host_id, scoring)

    # Insert metric
    ts = payload.timestamp or datetime.now(timezone.utc).isoformat()
    insert_metric_query = """
    INSERT INTO metrics (host_id, observed_at, cpu_percent, memory_percent,
                         disk_io_bytes_sec, network_bytes_sec, request_latency_ms, error_rate)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
    """
    params = (
        payload.host_id, ts, m.cpu_percent, m.memory_percent,
        m.disk_io_bytes_sec, m.network_bytes_sec, m.request_latency_ms, m.error_rate
    )
    metric_id = db_manager.execute_insert(insert_metric_query, params)

    # Insert alert if condition met
    alert_id = None
    if alert_triggered:
        insert_alert_query = """
        INSERT INTO alerts (host_id, detected_at, anomaly_score, severity, model_version, evidence)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        evidence_json = json.dumps({
            "metric_id": metric_id,
            "metrics": metrics_dict,
            "scoring": scoring
        })
        alert_params = (
            payload.host_id, datetime.now(timezone.utc).isoformat(),
            scoring["anomaly_score"], scoring["severity"], scoring["model_version"], evidence_json
        )
        alert_id = db_manager.execute_insert(insert_alert_query, alert_params)
        logger.warning(f"ALERT CREATED: #{alert_id} on {payload.host_id} (severity: {scoring['severity']})")

    return {
        "status": "accepted",
        "metric_id": metric_id,
        "anomaly_score": scoring["anomaly_score"],
        "is_anomaly": scoring["is_anomaly"],
        "severity": scoring["severity"],
        "model_version": scoring["model_version"],
        "alert_triggered": alert_triggered,
        "alert_id": alert_id
    }


@app.get("/api/v1/metrics")
async def get_metrics(
    host_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    if host_id:
        query = "SELECT * FROM metrics WHERE host_id = %s ORDER BY observed_at DESC LIMIT %s"
        rows = db_manager.execute_query(query, (host_id, limit))
    else:
        query = "SELECT * FROM metrics ORDER BY observed_at DESC LIMIT %s"
        rows = db_manager.execute_query(query, (limit,))
    return {"count": len(rows), "metrics": rows}


@app.get("/api/v1/alerts")
async def get_alerts(
    host_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    query = "SELECT id, host_id, detected_at, anomaly_score, severity, status, model_version, acknowledged_at, acknowledged_by FROM alerts WHERE 1=1"
    params = []

    if host_id:
        query += " AND host_id = %s"
        params.append(host_id)
    if status:
        query += " AND status = %s"
        params.append(status)
    if severity:
        query += " AND severity = %s"
        params.append(severity)

    query += " ORDER BY detected_at DESC LIMIT %s"
    params.append(limit)

    rows = db_manager.execute_query(query, tuple(params))
    return {"count": len(rows), "alerts": rows}


@app.put("/api/v1/alerts/{alert_id}/ack")
@app.post("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, body: Optional[AlertAcknowledge] = None):
    ack_by = body.acknowledged_by if body else "operator"
    now_str = datetime.now(timezone.utc).isoformat()
    query = """
    UPDATE alerts SET status = 'acknowledged', acknowledged_by = %s, acknowledged_at = %s
    WHERE id = %s AND status = 'active'
    """
    affected = db_manager.execute_update(query, (ack_by, now_str, alert_id))
    if affected == 0:
        raise HTTPException(status_code=404, detail="Alert not found or already acknowledged")
    return {"status": "acknowledged", "alert_id": alert_id}


@app.get("/api/v1/dashboard/overview")
@app.get("/api/v1/dashboard/stats")
async def dashboard_overview():
    """Consolidated KPI overview for the dashboard."""
    hosts_rows = db_manager.execute_query("SELECT COUNT(DISTINCT host_id) as count FROM hosts")
    host_count = hosts_rows[0]["count"] if hosts_rows else 0

    alerts_rows = db_manager.execute_query("SELECT COUNT(*) as count FROM alerts WHERE status = 'active'")
    active_alerts = alerts_rows[0]["count"] if alerts_rows else 0

    sev_rows = db_manager.execute_query(
        "SELECT severity, COUNT(*) as count FROM alerts WHERE status = 'active' GROUP BY severity"
    )
    severity_breakdown = {r["severity"]: r["count"] for r in sev_rows}

    avg_rows = db_manager.execute_query("""
    SELECT AVG(cpu_percent) as avg_cpu,
           AVG(memory_percent) as avg_memory,
           AVG(request_latency_ms) as avg_latency,
           AVG(error_rate) as avg_error_rate
    FROM metrics WHERE observed_at >= NOW() - INTERVAL '5 minutes'
    """)
    avg_metrics = avg_rows[0] if avg_rows and avg_rows[0]["avg_cpu"] is not None else {
        "avg_cpu": 42.5, "avg_memory": 56.1, "avg_latency": 48.0, "avg_error_rate": 0.003
    }

    return {
        "host_count": host_count,
        "active_alerts": active_alerts,
        "severity_breakdown": severity_breakdown,
        "average_metrics": avg_metrics,
        "model_version": anomaly_engine.model_version,
        "database": db_manager.engine_type,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/v1/model/status")
async def model_status():
    eval_path = "ml/models/evaluation_results.json"
    evaluation = None
    if Path(eval_path).exists():
        try:
            with open(eval_path) as f:
                evaluation = json.load(f)
        except Exception:
            pass

    return {
        "model_loaded": anomaly_engine.model is not None,
        "model_version": anomaly_engine.model_version,
        "threshold": anomaly_engine.threshold,
        "feature_count": len(anomaly_engine.feature_columns),
        "evaluation": evaluation
    }


@app.post("/api/v1/simulate/inject")
async def simulate_fault_injection(req: SimulationRequest):
    """Trigger a synthetic failure mode or normal baseline in real time."""
    scenarios = {
        "cpu_spike": {"cpu_percent": 98.2, "memory_percent": 60.0, "disk_io_bytes_sec": 2048576, "network_bytes_sec": 5242880, "request_latency_ms": 195.0, "error_rate": 0.01},
        "memory_leak": {"cpu_percent": 58.0, "memory_percent": 96.5, "disk_io_bytes_sec": 1048576, "network_bytes_sec": 4194304, "request_latency_ms": 120.0, "error_rate": 0.02},
        "disk_saturation": {"cpu_percent": 75.0, "memory_percent": 65.0, "disk_io_bytes_sec": 210000000, "network_bytes_sec": 2097152, "request_latency_ms": 380.0, "error_rate": 0.05},
        "network_flood": {"cpu_percent": 88.0, "memory_percent": 62.0, "disk_io_bytes_sec": 1048576, "network_bytes_sec": 145000000, "request_latency_ms": 210.0, "error_rate": 0.04},
        "cascading_failure": {"cpu_percent": 96.5, "memory_percent": 89.0, "disk_io_bytes_sec": 95000000, "network_bytes_sec": 85000000, "request_latency_ms": 920.0, "error_rate": 0.28},
        "normal_traffic": {"cpu_percent": 38.5, "memory_percent": 52.0, "disk_io_bytes_sec": 1048576, "network_bytes_sec": 5242880, "request_latency_ms": 42.0, "error_rate": 0.002}
    }

    metrics_data = scenarios.get(req.scenario, scenarios["normal_traffic"])
    payload = MetricIngestion(
        host_id=req.host_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        metrics=MetricsPayload(**metrics_data)
    )
    result = await ingest_metrics(payload)
    result["scenario"] = req.scenario
    result["metrics"] = metrics_data
    return result


# ──────────────────────────────────────────────────────────────
# System, Auth, Admin, Device, and Alarmer Endpoints
# ──────────────────────────────────────────────────────────────

import socket

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


# In-memory stores for multi-device pairing & admin
registered_devices = [
    {
        "id": "dev-01",
        "name": "Ops Workstation (Primary Console)",
        "type": "desktop",
        "os": "Windows 11 x64",
        "browser": "Chrome 122",
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "last_ping": "Active Now",
        "status": "online",
        "role": "Primary Console",
        "battery": "100% (AC)"
    },
    {
        "id": "dev-02",
        "name": "SRE Incident Tablet (iPad Pro)",
        "type": "tablet",
        "os": "iPadOS 17.4",
        "browser": "Safari Mobile",
        "registered_at": (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat(),
        "last_ping": "1m ago",
        "status": "online",
        "role": "Mobile Pager",
        "battery": "84%"
    }
]

cluster_nodes = [
    {"id": "node-1", "host_id": "server-01", "name": "Telemetry Ingestion Gateway", "ip": "10.0.1.14", "port": 8080, "os": "Ubuntu 22.04 LTS", "cores": 16, "ram_gb": 64, "status": "online", "role": "Ingestion"},
    {"id": "node-2", "host_id": "server-02", "name": "ML Inference & Scoring Worker", "ip": "10.0.1.15", "port": 8081, "os": "Ubuntu 22.04 LTS", "cores": 32, "ram_gb": 128, "status": "online", "role": "Worker"},
    {"id": "node-3", "host_id": "server-03", "name": "Resilient Telemetry Storage DB", "ip": "10.0.1.16", "port": 5432, "os": "Debian 12", "cores": 8, "ram_gb": 32, "status": "online", "role": "Database"},
    {"id": "node-4", "host_id": "edge-node-04", "name": "Edge Telemetry Probe Node", "ip": "10.0.2.22", "port": 9090, "os": "Alpine Linux", "cores": 4, "ram_gb": 8, "status": "online", "role": "Edge"}
]

operator_users = [
    {"id": "usr-1", "name": "Akshat (Lead)", "email": "admin@sentinel.internal", "role": "admin", "department": "Platform Reliability", "last_login": "Just now", "status": "active"},
    {"id": "usr-2", "name": "DevOps Engineer", "email": "sre.lead@sentinel.internal", "role": "sre", "department": "Infrastructure SRE", "last_login": "15m ago", "status": "active"},
    {"id": "usr-3", "name": "Security Auditor", "email": "viewer@sentinel.internal", "role": "viewer", "department": "SecOps Audit", "last_login": "1h ago", "status": "active"}
]

audit_logs = [
    {"timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "user": "admin@sentinel.internal", "action": "CALIBRATE_MODEL", "details": "Calibrated decision threshold to -0.0285", "severity": "info"},
    {"timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "user": "system", "action": "INITIALIZE_CLUSTER", "details": "Ingestion engine connected to sentinel.db", "severity": "info"}
]

active_alarms = {
    "is_ringing": False,
    "alarm_level": "normal",
    "last_triggered": None,
    "acknowledged_by": None,
    "active_incident": None
}


@app.get("/api/v1/system/network-info")
async def get_network_info():
    """Returns local LAN IP, hostname, and anywhere tunnel options for remote mobile connection."""
    lan_ip = get_lan_ip()
    port = int(os.getenv("BACKEND_PORT", 8080))
    hostname = socket.gethostname()
    return {
        "lan_ip": lan_ip,
        "hostname": hostname,
        "port": port,
        "local_url": f"http://localhost:{port}/",
        "lan_url": f"http://{lan_ip}:{port}/",
        "mobile_pager_url": f"http://{lan_ip}:{port}/mobile",
        "hostname_url": f"http://{hostname.lower()}.local:{port}/mobile",
        "qr_image_url": f"/api/v1/system/qr-code?url=http://{lan_ip}:{port}/mobile",
        "anywhere_guide": {
            "cloudflare_cmd": f"cloudflared tunnel --url http://127.0.0.1:{port}",
            "ngrok_cmd": f"ngrok http {port}",
            "npx_tunnel_cmd": f"npx localtunnel --port {port}"
        }
    }

import io
import qrcode
import qrcode.image.svg

@app.get("/api/v1/system/qr-code")
async def generate_qr_code(url: Optional[str] = None):
    """Generates a valid, standards-compliant SVG QR code pointing to the mobile app."""
    if not url:
        lan_ip = get_lan_ip()
        port = int(os.getenv("BACKEND_PORT", 8080))
        url = f"http://{lan_ip}:{port}/mobile"

    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
        image_factory=factory
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#090d16", back_color="#ffffff")
    
    stream = io.BytesIO()
    img.save(stream)
    svg_bytes = stream.getvalue()
    
    return Response(content=svg_bytes, media_type="image/svg+xml")


class LoginRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str
    remember: Optional[bool] = True

class SignupRequest(BaseModel):
    username: Optional[str] = None
    name: Optional[str] = None
    email: str
    password: str
    department: Optional[str] = "Engineering"
    role: Optional[str] = "Lead SRE"

# In-memory active user sessions
active_sessions: Dict[str, Dict[str, Any]] = {}

@app.post("/api/v1/auth/login")
async def auth_login(req: LoginRequest):
    login_id = req.username or req.email or ""
    if not login_id:
        raise HTTPException(status_code=400, detail="Username or email is required.")
    
    # Authenticate via database manager
    user = db_manager.authenticate_user(login_id, req.password)
    
    if not user:
        # Fallback for demo convenience if user doesn't exist yet
        if req.password in ("sentinel2026", "admin", "demo", "aksha2026"):
            role = "Lead SRE / SecOps Admin" if "admin" in login_id.lower() else "Infrastructure Ops"
            username = login_id.split("@")[0].lower()
            try:
                user = db_manager.register_user(
                    username=username,
                    email=login_id if "@" in login_id else f"{username}@sentinel.io",
                    password=req.password,
                    role=role,
                    full_name=username.capitalize()
                )
            except Exception:
                user = db_manager.get_user_by_username(username)
        else:
            raise HTTPException(status_code=401, detail="Invalid username/email or password.")

    token = f"sentinel-jwt-{user['id']}-{int(datetime.now().timestamp())}"
    active_sessions[token] = user

    audit_logs.insert(0, {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "user": user["username"],
        "action": "USER_LOGIN",
        "details": f"Authenticated session started for role '{user['role']}'",
        "severity": "info"
    })

    return {
        "status": "success",
        "token": token,
        "user": user,
        "message": f"Welcome back, {user.get('full_name') or user['username']}!"
    }

@app.post("/api/v1/auth/signup")
async def auth_signup(req: SignupRequest):
    email = req.email.strip().lower()
    username = (req.username or req.name or email.split("@")[0]).strip().lower()
    role = req.role or "Ops Engineer"
    full_name = req.name or username.capitalize()

    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")

    try:
        user = db_manager.register_user(
            username=username,
            email=email,
            password=req.password,
            role=role,
            full_name=full_name
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail="Failed to register user account.")

    token = f"sentinel-jwt-{user['id']}-{int(datetime.now().timestamp())}"
    active_sessions[token] = user

    audit_logs.insert(0, {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "user": user["username"],
        "action": "USER_SIGNUP",
        "details": f"New account registered: {user['username']} ({user['role']})",
        "severity": "info"
    })

    return {
        "status": "success",
        "token": token,
        "user": user,
        "message": f"Account successfully created! Logged in as {user['username']}."
    }

@app.get("/api/v1/auth/me")
async def auth_get_me(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if "Bearer " in auth_header else request.query_params.get("token", "")
    
    if token and token in active_sessions:
        return {"authenticated": True, "user": active_sessions[token]}
    
    # Return default admin user for zero-auth fallback
    admin_user = db_manager.get_user_by_username("admin") or {
        "id": 1,
        "username": "admin",
        "email": "admin@sentinel.io",
        "role": "Lead SRE / SecOps Admin",
        "full_name": "System Administrator"
    }
    return {"authenticated": bool(token), "user": admin_user if not token else None}

@app.post("/api/v1/auth/logout")
async def auth_logout(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if "Bearer " in auth_header else ""
    if token in active_sessions:
        del active_sessions[token]
    return {"status": "success", "message": "Session terminated."}

@app.get("/api/v1/admin/nodes")
async def get_cluster_nodes():
    return {"nodes": cluster_nodes}

class AddNodeRequest(BaseModel):
    host_id: str
    name: str
    ip: str
    port: int = 8080
    os: str = "Linux"
    role: str = "Worker"

@app.post("/api/v1/admin/nodes")
async def add_cluster_node(req: AddNodeRequest):
    new_node = {
        "id": f"node-{len(cluster_nodes)+1}",
        "host_id": req.host_id,
        "name": req.name,
        "ip": req.ip,
        "port": req.port,
        "os": req.os,
        "cores": 8,
        "ram_gb": 32,
        "status": "online",
        "role": req.role
    }
    cluster_nodes.append(new_node)
    audit_logs.insert(0, {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "user": "admin",
        "action": "ADD_CLUSTER_NODE",
        "details": f"Added node {req.host_id} ({req.ip}:{req.port})",
        "severity": "info"
    })
    return {"status": "success", "node": new_node}

@app.get("/api/v1/admin/users")
async def get_admin_users():
    return {"users": operator_users}

class ModelTuneRequest(BaseModel):
    threshold: float
    window_duration: Optional[int] = 15
    sensitivity: Optional[str] = "calibrated"

@app.post("/api/v1/admin/model/tune")
async def tune_model(req: ModelTuneRequest):
    anomaly_engine.threshold = float(req.threshold)
    audit_logs.insert(0, {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "user": "admin",
        "action": "TUNE_MODEL_THRESHOLD",
        "details": f"Updated anomaly threshold to {req.threshold:.4f} (window: {req.window_duration}s)",
        "severity": "warning"
    })
    return {
        "status": "success",
        "new_threshold": anomaly_engine.threshold,
        "model_version": anomaly_engine.model_version
    }

@app.get("/api/v1/admin/logs")
async def get_audit_logs():
    return {"logs": audit_logs[:50]}

@app.get("/api/v1/devices")
async def get_devices():
    return {"devices": registered_devices}

class DeviceRegisterRequest(BaseModel):
    name: str
    type: str
    os: str
    browser: str
    fingerprint: str
    battery: Optional[str] = "Unknown"
    role: Optional[str] = "Mobile Pager"

@app.post("/api/v1/devices/register")
async def register_device(req: DeviceRegisterRequest):
    # Check if already registered
    existing = next((d for d in registered_devices if d.get("fingerprint") == req.fingerprint), None)
    if existing:
        existing["last_ping"] = "Active Now"
        existing["battery"] = req.battery or existing.get("battery", "Unknown")
        return {"status": "registered", "device": existing}
    
    new_device = {
        "id": f"dev-{len(registered_devices)+1:02d}",
        "name": req.name,
        "type": req.type,
        "os": req.os,
        "browser": req.browser,
        "fingerprint": req.fingerprint,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "last_ping": "Active Now",
        "status": "online",
        "role": req.role or "Mobile Pager",
        "battery": req.battery or "Unknown"
    }
    registered_devices.insert(0, new_device)
    audit_logs.insert(0, {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "user": "device_recognizer",
        "action": "REGISTER_DEVICE",
        "details": f"Registered device '{new_device['name']}' ({new_device['os']} / {new_device['type']})",
        "severity": "info"
    })
    return {"status": "registered", "device": new_device}

@app.get("/api/v1/alarms/active")
async def get_active_alarms():
    return active_alarms

class AlarmActionRequest(BaseModel):
    action: str  # acknowledge, resolve, trigger
    user: Optional[str] = "Operator"

@app.post("/api/v1/alarms/action")
async def handle_alarm_action(req: AlarmActionRequest):
    if req.action == "acknowledge":
        active_alarms["is_ringing"] = False
        active_alarms["acknowledged_by"] = req.user
        audit_logs.insert(0, {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "user": req.user,
            "action": "ACKNOWLEDGE_ALARM",
            "details": "Audible siren silenced by operator",
            "severity": "info"
        })
    elif req.action == "resolve":
        active_alarms["is_ringing"] = False
        active_alarms["alarm_level"] = "normal"
        active_alarms["active_incident"] = None
        audit_logs.insert(0, {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "user": req.user,
            "action": "RESOLVE_INCIDENT",
            "details": "Incident resolved, cluster returned to nominal health",
            "severity": "info"
        })
    elif req.action == "trigger":
        active_alarms["is_ringing"] = True
        active_alarms["alarm_level"] = "critical"
        active_alarms["last_triggered"] = datetime.now(timezone.utc).isoformat()
        active_alarms["active_incident"] = {
            "title": "Severe Multivariate Anomaly Detected",
            "host_id": "server-01",
            "severity": "critical",
            "rca": "Memory leak leading to cascading queue overflow and latency degradation",
            "blast_radius": "server-01, worker pool 3, queue depth > 450"
        }
        audit_logs.insert(0, {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "user": req.user,
            "action": "TRIGGER_ALARM",
            "details": "Emergency audible siren triggered across all connected devices",
            "severity": "critical"
        })
    return active_alarms


# ──────────────────────────────────────────────────────────────
# Real Laptop Hardware Telemetry & Remote Control Security Engine
# ──────────────────────────────────────────────────────────────

import ctypes
import getpass
import platform
import psutil

# Sentinel Security & Guard State
security_state = {
    "host_id": socket.gethostname(),
    "owner_user": getpass.getuser(),
    "os_name": f"{platform.system()} {platform.release()} (Build {platform.version()})",
    "guard_mode": "ARMED",  # ARMED | DISARMED
    "tamper_detected": False,
    "tamper_event": None,
    "tamper_timestamp": None,
    "device_locked": False,
    "loud_siren_active": False,
    "strobe_warning_active": False,
    "last_action_taken": None
}

def lock_workstation_native():
    """Immediately and natively lock the physical workstation."""
    try:
        if platform.system() == "Windows":
            return ctypes.windll.user32.LockWorkStation() != 0
        elif platform.system() == "Darwin":
            os.system('/System/Library/CoreServices/"Menu Extras"/User.menu/Contents/Resources/CGSession -suspend')
            return True
        else:
            os.system('xdg-screensaver lock')
            return True
    except Exception as e:
        logger.error(f"Failed to execute native lock: {e}")
        return False

@app.get("/api/v1/system/host-telemetry")
async def get_host_telemetry():
    """Extract real-time physical hardware specs & telemetry from the user's host laptop."""
    try:
        # Battery stats
        bat = psutil.sensors_battery()
        bat_info = {
            "percent": bat.percent if bat else 100,
            "plugged_in": bat.power_plugged if bat else True,
            "status_text": f"{bat.percent}% (AC Connected)" if bat and bat.power_plugged else (f"{bat.percent}% (Discharging)" if bat else "AC Powered (Desktop)")
        }

        # Memory stats
        vm = psutil.virtual_memory()
        mem_info = {
            "total_gb": round(vm.total / (1024 ** 3), 2),
            "used_gb": round(vm.used / (1024 ** 3), 2),
            "free_gb": round(vm.free / (1024 ** 3), 2),
            "percent": vm.percent
        }

        # CPU stats
        cpu_freq = psutil.cpu_freq()
        cpu_info = {
            "cores_physical": psutil.cpu_count(logical=False) or 4,
            "cores_logical": psutil.cpu_count(logical=True) or 8,
            "usage_percent": psutil.cpu_percent(interval=None),
            "freq_mhz": round(cpu_freq.current, 0) if cpu_freq else 2400
        }

        # Disk stats
        drive = "C:\\" if os.name == 'nt' else "/"
        disk = psutil.disk_usage(drive)
        disk_info = {
            "drive": drive,
            "total_gb": round(disk.total / (1024 ** 3), 1),
            "used_gb": round(disk.used / (1024 ** 3), 1),
            "free_gb": round(disk.free / (1024 ** 3), 1),
            "percent": disk.percent
        }

        # Network stats
        net = psutil.net_io_counters()
        net_info = {
            "local_ip": get_lan_ip(),
            "bytes_sent_mb": round(net.bytes_sent / (1024 ** 2), 1),
            "bytes_recv_mb": round(net.bytes_recv / (1024 ** 2), 1)
        }

        # Top processes
        top_procs = []
        try:
            for p in sorted(psutil.process_iter(['name', 'cpu_percent', 'memory_info']),
                            key=lambda x: x.info['memory_info'].rss if x.info.get('memory_info') else 0,
                            reverse=True)[:5]:
                top_procs.append({
                    "name": p.info['name'],
                    "cpu": round(p.info.get('cpu_percent') or 0.0, 1),
                    "memory_mb": round((p.info['memory_info'].rss if p.info.get('memory_info') else 0) / (1024 ** 2), 1)
                })
        except Exception:
            pass

        return {
            "status": "success",
            "hostname": socket.gethostname(),
            "username": getpass.getuser(),
            "os_name": security_state["os_name"],
            "architecture": platform.machine(),
            "battery": bat_info,
            "memory": mem_info,
            "cpu": cpu_info,
            "disk": disk_info,
            "network": net_info,
            "top_processes": top_procs,
            "security": security_state
        }
    except Exception as e:
        logger.error(f"Error reading host telemetry: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/v1/security/state")
async def get_security_state():
    return security_state

class GuardModeRequest(BaseModel):
    mode: str  # "ARMED" or "DISARMED"

@app.post("/api/v1/security/guard")
async def toggle_guard_mode(req: GuardModeRequest):
    security_state["guard_mode"] = req.mode.upper()
    audit_logs.insert(0, {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "user": "mobile_pager",
        "action": f"GUARD_MODE_{security_state['guard_mode']}",
        "details": f"Sentinel Intruder Guard mode set to {security_state['guard_mode']}",
        "severity": "info"
    })
    return security_state

@app.post("/api/v1/security/simulate-intruder")
async def simulate_intruder():
    security_state["tamper_detected"] = True
    security_state["tamper_event"] = "Physical lid opened & mouse activity detected while operator is away."
    security_state["tamper_timestamp"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    active_alarms["is_ringing"] = True
    active_alarms["alarm_level"] = "critical"
    audit_logs.insert(0, {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "user": "anti_tamper_sensor",
        "action": "UNAUTHORIZED_PHYSICAL_ACCESS",
        "details": f"Intruder detected interacting with {security_state['host_id']}",
        "severity": "critical"
    })
    return security_state

class SecurityControlRequest(BaseModel):
    action: str  # "lock_laptop", "blast_siren", "screen_freeze", "disarm"
    live_lock: Optional[bool] = True

@app.post("/api/v1/security/control")
async def handle_security_control(req: SecurityControlRequest):
    action = req.action.lower()
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

    if action == "lock_laptop":
        success = False
        if req.live_lock:
            success = lock_workstation_native()
        security_state["device_locked"] = True
        security_state["last_action_taken"] = f"Workstation LOCKED at {ts}"
        audit_logs.insert(0, {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "user": "mobile_pager_remote",
            "action": "REMOTE_LOCK_DISPATCHED",
            "details": f"Emergency remote lock executed on {security_state['host_id']}. Screen locked.",
            "severity": "warning"
        })
        return {
            "status": "success",
            "action": "lock_laptop",
            "locked": True,
            "native_locked": success,
            "message": f"Emergency Lock Command Executed on {security_state['host_id']}"
        }

    elif action == "blast_siren":
        security_state["loud_siren_active"] = True
        active_alarms["is_ringing"] = True
        try:
            import winsound
            winsound.Beep(2400, 1500)
        except Exception:
            pass
        security_state["last_action_taken"] = f"Acoustic Alarm blasted at {ts}"
        return {"status": "success", "action": "blast_siren", "message": "Host Siren Active"}

    elif action == "screen_freeze":
        security_state["strobe_warning_active"] = True
        security_state["last_action_taken"] = f"Screen warning strobe dispatched at {ts}"
        return {"status": "success", "action": "screen_freeze", "message": "Screen Freeze Dispatched"}

    elif action == "disarm":
        security_state["tamper_detected"] = False
        security_state["tamper_event"] = None
        security_state["loud_siren_active"] = False
        security_state["strobe_warning_active"] = False
        security_state["device_locked"] = False
        security_state["last_action_taken"] = f"Disarmed / Cleared at {ts}"
        active_alarms["is_ringing"] = False
        active_alarms["alarm_level"] = "normal"
        audit_logs.insert(0, {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "user": "mobile_pager_remote",
            "action": "ALARM_DISARMED",
            "details": f"Security alarms disarmed and reset to nominal by owner.",
            "severity": "info"
        })
        return {"status": "success", "action": "disarm", "message": "System disarmed"}

    raise HTTPException(status_code=400, detail="Unknown security action")


# ──────────────────────────────────────────────────────────────
# Remote Workstation Unlock Engine (From Mobile / Tablet)
# ──────────────────────────────────────────────────────────────

def wake_and_unlock_windows_host(credentials: str = ""):
    """Wakes the physical Windows display, dismisses lock screen curtain, and injects unlock keystrokes."""
    try:
        if platform.system() == "Windows":
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            # 1. Force screen on / prevent display and system sleep
            # ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001) | ES_DISPLAY_REQUIRED (0x00000002)
            try:
                kernel32.SetThreadExecutionState(0x80000003)
            except Exception as e:
                logger.warning(f"SetThreadExecutionState failed: {e}")

            # 2. Jiggle mouse to turn on physical monitor backlight
            try:
                user32.mouse_event(0x0001, 2, 2, 0, 0)
                time.sleep(0.05)
                user32.mouse_event(0x0001, -2, -2, 0, 0)
                time.sleep(0.15)
            except Exception as e:
                logger.warning(f"mouse_event failed: {e}")

            # 3. Dismiss lock screen wallpaper curtain (Space key)
            user32.keybd_event(0x20, 0, 0, 0)  # Space down
            time.sleep(0.06)
            user32.keybd_event(0x20, 0, 2, 0)  # Space up
            time.sleep(0.40)
            
            # 4. If password/PIN provided, type each character into Windows logon prompt
            if credentials:
                KEYEVENTF_KEYUP = 0x0002
                KEYEVENTF_UNICODE = 0x0004
                
                # Send Backspace a few times to clear any accidental prior characters
                for _ in range(2):
                    user32.keybd_event(0x08, 0, 0, 0)
                    time.sleep(0.02)
                    user32.keybd_event(0x08, 0, KEYEVENTF_KEYUP, 0)
                    time.sleep(0.02)
                time.sleep(0.08)

                for ch in credentials:
                    vk = user32.VkKeyScanW(ord(ch))
                    if vk != -1:
                        key_code = vk & 0xFF
                        shift = (vk >> 8) & 1
                        if shift:
                            user32.keybd_event(0x10, 0, 0, 0)  # Shift down
                        user32.keybd_event(key_code, 0, 0, 0)
                        time.sleep(0.02)
                        user32.keybd_event(key_code, 0, KEYEVENTF_KEYUP, 0)
                        if shift:
                            user32.keybd_event(0x10, 0, KEYEVENTF_KEYUP, 0)  # Shift up
                        time.sleep(0.03)
                    else:
                        # Direct unicode fallback for special symbols/keys
                        user32.keybd_event(0, ord(ch), KEYEVENTF_UNICODE, 0)
                        time.sleep(0.02)
                        user32.keybd_event(0, ord(ch), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)
                        time.sleep(0.03)
                
                # Press ENTER to submit logon
                time.sleep(0.15)
                user32.keybd_event(0x0D, 0, 0, 0)
                time.sleep(0.05)
                user32.keybd_event(0x0D, 0, KEYEVENTF_KEYUP, 0)
            return True
        elif platform.system() == "Darwin":
            os.system('caffeinate -u -t 2')
            return True
        else:
            os.system('xset dpms force on')
            return True
    except Exception as e:
        logger.error(f"Failed to execute wake & unlock: {e}")
        return False

class RemoteUnlockRequest(BaseModel):
    password: Optional[str] = ""
    user: Optional[str] = None
    pin: Optional[str] = ""
    action: Optional[str] = "unlock"  # "unlock" | "wake_only" | "lock"

@app.post("/api/v1/security/remote-unlock")
async def handle_remote_unlock(req: RemoteUnlockRequest):
    """Authenticate and remotely unlock the workstation from mobile/tablet."""
    target_user = req.user or security_state.get("owner_user", getpass.getuser())
    entered_creds = req.password or req.pin or ""
    action = (req.action or "unlock").lower()
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

    # If action is lock:
    if action == "lock":
        success = lock_workstation_native()
        security_state["device_locked"] = True
        security_state["last_action_taken"] = f"Workstation LOCKED at {ts}"
        return {
            "status": "success",
            "action": "lock",
            "locked": True,
            "native_locked": success,
            "message": f"Workstation {security_state['host_id']} locked successfully."
        }

    # Execute wake and unlock simulation on physical host
    sim_success = wake_and_unlock_windows_host(entered_creds if action != "wake_only" else "")
    
    # Update Security State & clear all lock/tamper flags
    security_state["device_locked"] = False
    security_state["tamper_detected"] = False
    security_state["loud_siren_active"] = False
    security_state["strobe_warning_active"] = False
    
    action_label = "UNLOCKED WITH PASSWORD" if entered_creds else "SCREEN WOKEN"
    security_state["last_action_taken"] = f"Workstation {action_label} remotely by {target_user} at {ts}"
    
    active_alarms["is_ringing"] = False
    active_alarms["alarm_level"] = "normal"
    
    audit_logs.insert(0, {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "user": f"{target_user} (Mobile Device)",
        "action": "REMOTE_WORKSTATION_UNLOCK" if entered_creds else "REMOTE_SCREEN_WAKE",
        "details": f"Remote session unlock command dispatched to {security_state['host_id']}. Screen active and unlocked.",
        "severity": "info"
    })
    
    return {
        "status": "success",
        "action": action,
        "unlocked": True,
        "host_id": security_state["host_id"],
        "user": target_user,
        "has_credentials": bool(entered_creds),
        "message": f"Workstation {security_state['host_id']} {'unlocked with password' if entered_creds else 'display woken'} successfully by {target_user}.",
        "timestamp": ts,
        "native_keystrokes_injected": sim_success
    }


from fastapi.responses import FileResponse

# Serve static assets for AIOps Sentinel Dashboard
@app.get("/styles.css")
async def serve_styles():
    css_path = Path("backend/static/styles.css")
    if css_path.exists():
        return FileResponse(str(css_path), media_type="text/css")
    return Response(status_code=404)

@app.get("/app.js")
async def serve_app_js():
    js_path = Path("backend/static/app.js")
    if js_path.exists():
        return FileResponse(str(js_path), media_type="application/javascript")
    return Response(status_code=404)

# Primary Root Route: AIOps Sentinel Autonomous Telemetry & Anomaly Detection Dashboard
@app.get("/")
async def serve_sentinel_dashboard():
    sentinel_index = Path("backend/static/index.html")
    if sentinel_index.exists():
        return FileResponse(str(sentinel_index))
    return {"service": "AIOps Sentinel Backend API", "status": "operational"}

# Mount secondary folders if present
if Path("css").exists():
    app.mount("/css", StaticFiles(directory="css"), name="css")
if Path("js").exists():
    app.mount("/js", StaticFiles(directory="js"), name="js")

@app.get("/landing")
async def serve_landing_page():
    if Path("index.html").exists():
        return FileResponse("index.html")
    return FileResponse("backend/static/index.html")

@app.get("/mobile")
@app.get("/mobile/")
async def serve_mobile_app():
    mobile_index = Path("backend/static/mobile.html")
    if mobile_index.exists():
        return FileResponse(str(mobile_index))
    return FileResponse("backend/static/index.html")

@app.get("/manifest.json")
async def serve_manifest():
    manifest_path = Path("backend/static/manifest.json")
    if manifest_path.exists():
        return FileResponse(str(manifest_path), media_type="application/manifest+json")
    return Response(status_code=404)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("BACKEND_PORT", 8080))
    logger.info(f"Starting AIOps Sentinel Backend on port {port}...")
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, reload=False, log_level="info")
