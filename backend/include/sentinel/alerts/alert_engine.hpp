#pragma once
/**
 * alert_engine.hpp — Alert generation and lifecycle management
 *
 * Decides when to generate alerts based on:
 *   - Anomaly score threshold
 *   - Consecutive anomaly count (N observations in a row)
 *   - Cooldown period (suppress repeated alerts)
 *   - Severity classification
 */

#include <chrono>
#include <mutex>
#include <string>
#include <unordered_map>
#include "sentinel/models/metric.hpp"

namespace sentinel::alerts {

struct AlertConfig {
    double critical_threshold{-0.35};
    double warning_threshold{-0.15};
    double info_threshold{-0.05};
    int min_consecutive{2};
    int cooldown_seconds{120};
};

class AlertEngine {
public:
    explicit AlertEngine(const AlertConfig& config = AlertConfig{});

    /**
     * Process an anomaly result and determine if an alert should fire.
     * Returns true if a new alert should be created.
     */
    bool shouldAlert(const std::string& host_id,
                     const sentinel::models::AnomalyResult& result);

    /**
     * Classify severity based on anomaly score.
     */
    std::string classifySeverity(double anomaly_score) const;

    /**
     * Reset state for a host (e.g., after manual acknowledgement).
     */
    void resetHost(const std::string& host_id);

    /**
     * Get the consecutive anomaly count for a host.
     */
    int getConsecutiveCount(const std::string& host_id) const;

private:
    AlertConfig config_;
    mutable std::mutex mutex_;

    struct HostState {
        int consecutive_count{0};
        std::chrono::system_clock::time_point last_alert_time;
        bool in_cooldown{false};
    };

    std::unordered_map<std::string, HostState> host_states_;
};

}  // namespace sentinel::alerts
