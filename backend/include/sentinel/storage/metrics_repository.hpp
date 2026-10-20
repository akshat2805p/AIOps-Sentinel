#pragma once
/**
 * metrics_repository.hpp — Database persistence layer
 *
 * Handles all PostgreSQL interactions for metrics, hosts, and alerts.
 * Uses connection pooling via Drogon's built-in database client.
 */

#include <functional>
#include <memory>
#include <vector>
#include <drogon/drogon.h>
#include "sentinel/models/metric.hpp"

namespace sentinel::storage {

class MetricsRepository {
public:
    using MetricCallback = std::function<void(bool success, int64_t id)>;
    using MetricsListCallback = std::function<void(
        std::vector<sentinel::models::Metric>)>;
    using AlertCallback = std::function<void(bool success, int64_t id)>;

    MetricsRepository();

    /**
     * Insert a new metric observation.
     */
    void insertMetric(const sentinel::models::Metric& metric,
                      MetricCallback callback);

    /**
     * Retrieve the latest N metrics, optionally filtered by host.
     */
    void getLatestMetrics(const std::string& host_id, int limit,
                          MetricsListCallback callback);

    /**
     * Register or update a host.
     */
    void upsertHost(const std::string& host_id,
                    const std::string& hostname,
                    std::function<void(bool)> callback);

    /**
     * Insert an alert record.
     */
    void insertAlert(const sentinel::models::Alert& alert,
                     AlertCallback callback);

    /**
     * Acknowledge an alert by ID.
     */
    void acknowledgeAlert(int64_t alert_id,
                          const std::string& acknowledged_by,
                          std::function<void(bool)> callback);

private:
    drogon::orm::DbClientPtr db_client_;
};

}  // namespace sentinel::storage
