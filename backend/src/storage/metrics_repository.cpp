/**
 * metrics_repository.cpp — PostgreSQL data access layer
 */

#include "sentinel/storage/metrics_repository.hpp"
#include <drogon/drogon.h>

namespace sentinel::storage {

MetricsRepository::MetricsRepository() {
    db_client_ = drogon::app().getDbClient();
}

void MetricsRepository::insertMetric(
    const sentinel::models::Metric& metric,
    MetricCallback callback) {

    auto time_t = std::chrono::system_clock::to_time_t(metric.observed_at);
    char ts_buf[64];
    std::strftime(ts_buf, sizeof(ts_buf), "%Y-%m-%d %H:%M:%S",
                  std::gmtime(&time_t));

    db_client_->execSqlAsync(
        "INSERT INTO metrics "
        "(host_id, observed_at, cpu_percent, memory_percent, "
        " disk_io_bytes_sec, network_bytes_sec, "
        " request_latency_ms, error_rate) "
        "VALUES ($1, $2::timestamptz, $3, $4, $5, $6, $7, $8) "
        "RETURNING id",
        [callback](const drogon::orm::Result& result) {
            if (!result.empty()) {
                int64_t id = result[0]["id"].as<int64_t>();
                callback(true, id);
            } else {
                callback(false, 0);
            }
        },
        [callback](const drogon::orm::DrogonDbException& e) {
            LOG_ERROR << "Insert metric failed: " << e.base().what();
            callback(false, 0);
        },
        metric.host_id,
        std::string(ts_buf),
        metric.cpu_percent,
        metric.memory_percent,
        metric.disk_io_bytes_sec,
        metric.network_bytes_sec,
        metric.request_latency_ms,
        metric.error_rate
    );
}

void MetricsRepository::getLatestMetrics(
    const std::string& host_id, int limit,
    MetricsListCallback callback) {

    std::string query;
    if (host_id.empty()) {
        query = "SELECT * FROM metrics ORDER BY observed_at DESC LIMIT $1";
        db_client_->execSqlAsync(
            query,
            [callback](const drogon::orm::Result& result) {
                std::vector<sentinel::models::Metric> metrics;
                for (const auto& row : result) {
                    sentinel::models::Metric m;
                    m.id = row["id"].as<int64_t>();
                    m.host_id = row["host_id"].as<std::string>();
                    m.cpu_percent = row["cpu_percent"].as<double>();
                    m.memory_percent = row["memory_percent"].as<double>();
                    m.disk_io_bytes_sec = row["disk_io_bytes_sec"].as<double>();
                    m.network_bytes_sec = row["network_bytes_sec"].as<double>();
                    m.request_latency_ms = row["request_latency_ms"].as<double>();
                    m.error_rate = row["error_rate"].as<double>();
                    metrics.push_back(m);
                }
                callback(metrics);
            },
            [callback](const drogon::orm::DrogonDbException& e) {
                LOG_ERROR << "Get metrics failed: " << e.base().what();
                callback({});
            },
            limit
        );
    } else {
        query = "SELECT * FROM metrics WHERE host_id = $1 "
                "ORDER BY observed_at DESC LIMIT $2";
        db_client_->execSqlAsync(
            query,
            [callback](const drogon::orm::Result& result) {
                std::vector<sentinel::models::Metric> metrics;
                for (const auto& row : result) {
                    sentinel::models::Metric m;
                    m.id = row["id"].as<int64_t>();
                    m.host_id = row["host_id"].as<std::string>();
                    m.cpu_percent = row["cpu_percent"].as<double>();
                    m.memory_percent = row["memory_percent"].as<double>();
                    m.disk_io_bytes_sec = row["disk_io_bytes_sec"].as<double>();
                    m.network_bytes_sec = row["network_bytes_sec"].as<double>();
                    m.request_latency_ms = row["request_latency_ms"].as<double>();
                    m.error_rate = row["error_rate"].as<double>();
                    metrics.push_back(m);
                }
                callback(metrics);
            },
            [callback](const drogon::orm::DrogonDbException& e) {
                LOG_ERROR << "Get metrics failed: " << e.base().what();
                callback({});
            },
            host_id, limit
        );
    }
}

void MetricsRepository::upsertHost(
    const std::string& host_id, const std::string& hostname,
    std::function<void(bool)> callback) {

    db_client_->execSqlAsync(
        "INSERT INTO hosts (host_id, hostname) VALUES ($1, $2) "
        "ON CONFLICT (host_id) DO UPDATE SET last_seen_at = NOW()",
        [callback](const drogon::orm::Result&) {
            callback(true);
        },
        [callback](const drogon::orm::DrogonDbException& e) {
            LOG_ERROR << "Upsert host failed: " << e.base().what();
            callback(false);
        },
        host_id, hostname
    );
}

void MetricsRepository::insertAlert(
    const sentinel::models::Alert& alert,
    AlertCallback callback) {

    db_client_->execSqlAsync(
        "INSERT INTO alerts "
        "(host_id, anomaly_score, severity, model_version, evidence) "
        "VALUES ($1, $2, $3, $4, $5::jsonb) "
        "RETURNING id",
        [callback](const drogon::orm::Result& result) {
            if (!result.empty()) {
                callback(true, result[0]["id"].as<int64_t>());
            } else {
                callback(false, 0);
            }
        },
        [callback](const drogon::orm::DrogonDbException& e) {
            LOG_ERROR << "Insert alert failed: " << e.base().what();
            callback(false, 0);
        },
        alert.host_id,
        alert.anomaly_score,
        alert.severity,
        alert.model_version,
        Json::FastWriter().write(alert.evidence)
    );
}

void MetricsRepository::acknowledgeAlert(
    int64_t alert_id, const std::string& acknowledged_by,
    std::function<void(bool)> callback) {

    db_client_->execSqlAsync(
        "UPDATE alerts SET status = 'acknowledged', "
        "acknowledged_by = $1, acknowledged_at = NOW() "
        "WHERE id = $2 AND status = 'active'",
        [callback](const drogon::orm::Result& result) {
            callback(result.affectedRows() > 0);
        },
        [callback](const drogon::orm::DrogonDbException& e) {
            LOG_ERROR << "Acknowledge alert failed: " << e.base().what();
            callback(false);
        },
        acknowledged_by,
        alert_id
    );
}

}  // namespace sentinel::storage
