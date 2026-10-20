/**
 * metric_validator.cpp — Validation logic for incoming telemetry
 */

#include "sentinel/ingestion/metric_validator.hpp"

namespace sentinel::ingestion {

std::vector<ValidationError> MetricValidator::validate(
    const sentinel::models::Metric& metric) const {

    std::vector<ValidationError> errors;
    validateHostId(metric.host_id, errors);
    validateRanges(metric, errors);
    return errors;
}

bool MetricValidator::isValid(
    const sentinel::models::Metric& metric) const {
    return validate(metric).empty();
}

bool MetricValidator::validateHostId(
    const std::string& host_id,
    std::vector<ValidationError>& errors) const {

    if (host_id.empty()) {
        errors.push_back({"host_id", "host_id is required"});
        return false;
    }
    if (host_id.length() > 128) {
        errors.push_back({"host_id", "host_id exceeds 128 characters"});
        return false;
    }
    // Only allow alphanumeric, hyphens, underscores, and dots
    for (char c : host_id) {
        if (!std::isalnum(c) && c != '-' && c != '_' && c != '.') {
            errors.push_back({"host_id",
                "host_id contains invalid characters"});
            return false;
        }
    }
    return true;
}

bool MetricValidator::validateRanges(
    const sentinel::models::Metric& metric,
    std::vector<ValidationError>& errors) const {

    bool valid = true;

    if (metric.cpu_percent < 0.0 || metric.cpu_percent > 100.0) {
        errors.push_back({"cpu_percent",
            "cpu_percent must be between 0 and 100"});
        valid = false;
    }

    if (metric.memory_percent < 0.0 || metric.memory_percent > 100.0) {
        errors.push_back({"memory_percent",
            "memory_percent must be between 0 and 100"});
        valid = false;
    }

    if (metric.disk_io_bytes_sec < 0.0) {
        errors.push_back({"disk_io_bytes_sec",
            "disk_io_bytes_sec must be non-negative"});
        valid = false;
    }

    if (metric.network_bytes_sec < 0.0) {
        errors.push_back({"network_bytes_sec",
            "network_bytes_sec must be non-negative"});
        valid = false;
    }

    if (metric.request_latency_ms < 0.0) {
        errors.push_back({"request_latency_ms",
            "request_latency_ms must be non-negative"});
        valid = false;
    }

    if (metric.error_rate < 0.0 || metric.error_rate > 1.0) {
        errors.push_back({"error_rate",
            "error_rate must be between 0 and 1"});
        valid = false;
    }

    return valid;
}

}  // namespace sentinel::ingestion
