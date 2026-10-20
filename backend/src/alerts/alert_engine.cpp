/**
 * alert_engine.cpp — Alert generation and lifecycle management implementation
 */

#include "sentinel/alerts/alert_engine.hpp"

namespace sentinel::alerts {

AlertEngine::AlertEngine(const AlertConfig& config)
    : config_(config) {}

bool AlertEngine::shouldAlert(const std::string& host_id,
                             const sentinel::models::AnomalyResult& result) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto now = std::chrono::system_clock::now();
    auto& state = host_states_[host_id];

    if (!result.is_anomaly) {
        // Recovering / healthy reading resets consecutive counter
        state.consecutive_count = 0;
        return false;
    }

    state.consecutive_count++;

    // Check if cooldown period is active
    if (state.last_alert_time.time_since_epoch().count() > 0) {
        auto elapsed_seconds = std::chrono::duration_cast<std::chrono::seconds>(
            now - state.last_alert_time).count();
        if (elapsed_seconds < config_.cooldown_seconds) {
            state.in_cooldown = true;
            return false;
        }
    }
    state.in_cooldown = false;

    // Trigger alert if consecutive threshold is reached
    if (state.consecutive_count >= config_.min_consecutive) {
        state.last_alert_time = now;
        return true;
    }

    return false;
}

std::string AlertEngine::classifySeverity(double anomaly_score) const {
    if (anomaly_score < config_.critical_threshold) {
        return "critical";
    }
    if (anomaly_score < config_.warning_threshold) {
        return "warning";
    }
    if (anomaly_score < config_.info_threshold) {
        return "info";
    }
    return "normal";
}

void AlertEngine::resetHost(const std::string& host_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    host_states_.erase(host_id);
}

int AlertEngine::getConsecutiveCount(const std::string& host_id) const {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = host_states_.find(host_id);
    if (it != host_states_.end()) {
        return it->second.consecutive_count;
    }
    return 0;
}

}  // namespace sentinel::alerts
