-- 001_metrics.sql
-- Initial schema: hosts table and time-series metrics storage

BEGIN;

CREATE TABLE IF NOT EXISTS hosts (
    host_id     TEXT PRIMARY KEY,
    hostname    TEXT NOT NULL,
    ip_address  TEXT,
    os_info     TEXT,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS metrics (
    id                  BIGSERIAL PRIMARY KEY,
    host_id             TEXT NOT NULL REFERENCES hosts(host_id) ON DELETE CASCADE,
    observed_at         TIMESTAMPTZ NOT NULL,
    cpu_percent         REAL NOT NULL CHECK (cpu_percent >= 0 AND cpu_percent <= 100),
    memory_percent      REAL NOT NULL CHECK (memory_percent >= 0 AND memory_percent <= 100),
    disk_io_bytes_sec   DOUBLE PRECISION NOT NULL CHECK (disk_io_bytes_sec >= 0),
    network_bytes_sec   DOUBLE PRECISION NOT NULL CHECK (network_bytes_sec >= 0),
    request_latency_ms  REAL NOT NULL CHECK (request_latency_ms >= 0),
    error_rate          REAL NOT NULL CHECK (error_rate >= 0 AND error_rate <= 1),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Composite index for fast host+time range lookups (most common query pattern)
CREATE INDEX idx_metrics_host_time ON metrics (host_id, observed_at DESC);

-- Partial index for recent data queries (dashboard fetches last N hours)
CREATE INDEX idx_metrics_recent ON metrics (observed_at DESC)
    WHERE observed_at > NOW() - INTERVAL '7 days';

COMMIT;
