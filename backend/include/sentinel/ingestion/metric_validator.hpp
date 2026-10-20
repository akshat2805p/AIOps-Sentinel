#pragma once
/**
 * metric_validator.hpp — Input validation for incoming telemetry
 *
 * Validates range constraints, required fields, and data consistency
 * before metrics enter the processing pipeline.
 */

#include <string>
#include <vector>
#include "sentinel/models/metric.hpp"

namespace sentinel::ingestion {

struct ValidationError {
    std::string field;
    std::string message;
};

class MetricValidator {
public:
    /**
     * Validate a metric observation.  Returns a list of errors
     * (empty list = valid).
     */
    std::vector<ValidationError> validate(
        const sentinel::models::Metric& metric) const;

    /**
     * Quick check — true if all validations pass.
     */
    bool isValid(const sentinel::models::Metric& metric) const;

private:
    bool validateHostId(const std::string& host_id,
                        std::vector<ValidationError>& errors) const;
    bool validateRanges(const sentinel::models::Metric& metric,
                        std::vector<ValidationError>& errors) const;
};

}  // namespace sentinel::ingestion
