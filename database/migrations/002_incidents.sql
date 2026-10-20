-- 002_incidents.sql
-- Incident tracking for supervised risk-prediction training

BEGIN;

CREATE TABLE IF NOT EXISTS incidents (
    id              BIGSERIAL PRIMARY KEY,
    host_id         TEXT NOT NULL REFERENCES hosts(host_id) ON DELETE CASCADE,
    started_at      TIMESTAMPTZ NOT NULL,
    resolved_at     TIMESTAMPTZ,
    severity        TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    category        TEXT NOT NULL DEFAULT 'unknown',
    description     TEXT,
    root_cause      TEXT,
    is_synthetic    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_incidents_host_time ON incidents (host_id, started_at DESC);
CREATE INDEX idx_incidents_severity ON incidents (severity);
CREATE INDEX idx_incidents_open ON incidents (host_id)
    WHERE resolved_at IS NULL;

COMMIT;
