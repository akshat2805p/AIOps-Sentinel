-- 003_alerts.sql
-- Alert storage with anomaly scoring and acknowledgement workflow

BEGIN;

CREATE TABLE IF NOT EXISTS alerts (
    id              BIGSERIAL PRIMARY KEY,
    host_id         TEXT NOT NULL REFERENCES hosts(host_id) ON DELETE CASCADE,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    anomaly_score   REAL NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'acknowledged', 'resolved', 'suppressed')),
    model_version   TEXT NOT NULL,
    evidence        JSONB NOT NULL DEFAULT '{}'::jsonb,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    notes           TEXT
);

CREATE INDEX idx_alerts_host_time ON alerts (host_id, detected_at DESC);
CREATE INDEX idx_alerts_status ON alerts (status)
    WHERE status = 'active';
CREATE INDEX idx_alerts_severity ON alerts (severity, detected_at DESC);

-- View for quick dashboard summaries
CREATE OR REPLACE VIEW active_alerts_summary AS
SELECT
    host_id,
    COUNT(*) AS active_count,
    MAX(anomaly_score) AS max_score,
    MIN(detected_at) AS earliest_detection,
    MAX(detected_at) AS latest_detection
FROM alerts
WHERE status = 'active'
GROUP BY host_id;

COMMIT;
