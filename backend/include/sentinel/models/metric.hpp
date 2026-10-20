#pragma once
/**
 * metric.hpp — Core data structures for the telemetry pipeline
 *
 * Defines the Metric struct that flows through the entire system:
 * ingestion → validation → storage → inference → alerting
 */

#include <chrono>
#include <cstdint>
#include <string>
#include <optional>
#include <drogon/drogon.h>

namespace sentinel::models {

/**
 * Represents a single telemetry observation from a monitored host.
 * All numeric fields use double precision to match PostgreSQL's
 * DOUBLE PRECISION / REAL types.
 */
struct Metric {
    int64_t id{0};
    std::string host_id;
    std::chrono::system_clock::time_point observed_at;
    double cpu_percent{0.0};
    double memory_percent{0.0};
    double disk_io_bytes_sec{0.0};
    double network_bytes_sec{0.0};
    double request_latency_ms{0.0};
    double error_rate{0.0};

    /**
     * Serialize to JSON for API responses.
     */
    Json::Value toJson() const {
        Json::Value json;
        json["id"] = static_cast<Json::Int64>(id);
        json["host_id"] = host_id;

        // Format timestamp as ISO 8601
        auto time_t = std::chrono::system_clock::to_time_t(observed_at);
        char buf[64];
        std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ",
                      std::gmtime(&time_t));
        json["observed_at"] = buf;

        json["cpu_percent"] = cpu_percent;
        json["memory_percent"] = memory_percent;
        json["disk_io_bytes_sec"] = disk_io_bytes_sec;
        json["network_bytes_sec"] = network_bytes_sec;
        json["request_latency_ms"] = request_latency_ms;
        json["error_rate"] = error_rate;
        return json;
    }

    /**
     * Deserialize from a JSON request body.
     */
    static std::optional<Metric> fromJson(const Json::Value& json) {
        Metric m;
        if (!json.isMember("host_id") || !json.isMember("metrics")) {
            return std::nullopt;
        }

        m.host_id = json["host_id"].asString();

        if (json.isMember("timestamp")) {
            // Parse ISO 8601 timestamp — simplified for common format
            std::string ts = json["timestamp"].asString();
            std::tm tm = {};
            std::istringstream ss(ts);
            ss >> std::get_time(&tm, "%Y-%m-%dT%H:%M:%S");
            m.observed_at = std::chrono::system_clock::from_time_t(
                std::mktime(&tm));
        } else {
            m.observed_at = std::chrono::system_clock::now();
        }

        const auto& metrics = json["metrics"];
        m.cpu_percent = metrics.get("cpu_percent", 0.0).asDouble();
        m.memory_percent = metrics.get("memory_percent", 0.0).asDouble();
        m.disk_io_bytes_sec = metrics.get("disk_io_bytes_sec", 0.0).asDouble();
        m.network_bytes_sec = metrics.get("network_bytes_sec", 0.0).asDouble();
        m.request_latency_ms = metrics.get("request_latency_ms", 0.0).asDouble();
        m.error_rate = metrics.get("error_rate", 0.0).asDouble();

        return m;
    }
};

/**
 * Anomaly detection result for a single observation.
 */
struct AnomalyResult {
    double anomaly_score{0.0};
    bool is_anomaly{false};
    std::string severity{"normal"};
    std::string model_version{"unknown"};

    Json::Value toJson() const {
        Json::Value json;
        json["anomaly_score"] = anomaly_score;
        json["is_anomaly"] = is_anomaly;
        json["severity"] = severity;
        json["model_version"] = model_version;
        return json;
    }
};

/**
 * Alert generated when anomalous behavior is confirmed.
 */
struct Alert {
    int64_t id{0};
    std::string host_id;
    std::chrono::system_clock::time_point detected_at;
    double anomaly_score{0.0};
    std::string severity;
    std::string status{"active"};
    std::string model_version;
    Json::Value evidence;

    Json::Value toJson() const {
        Json::Value json;
        json["id"] = static_cast<Json::Int64>(id);
        json["host_id"] = host_id;
        json["anomaly_score"] = anomaly_score;
        json["severity"] = severity;
        json["status"] = status;
        json["model_version"] = model_version;
        json["evidence"] = evidence;

        auto time_t = std::chrono::system_clock::to_time_t(detected_at);
        char buf[64];
        std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ",
                      std::gmtime(&time_t));
        json["detected_at"] = buf;
        return json;
    }
};

}  // namespace sentinel::models
