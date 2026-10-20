#include <catch2/catch_test_macros.hpp>
#include "sentinel/ingestion/metric_validator.hpp"

TEST_CASE("MetricValidator accepts valid metrics", "[validator]") {
    sentinel::ingestion::MetricValidator validator;
    sentinel::models::Metric metric;
    metric.host_id = "prod-web-01";
    metric.cpu_percent = 45.2;
    metric.memory_percent = 62.1;
    metric.disk_io_bytes_sec = 1048576.0;
    metric.network_bytes_sec = 5242880.0;
    metric.request_latency_ms = 45.0;
    metric.error_rate = 0.005;

    REQUIRE(validator.isValid(metric));
    auto errors = validator.validate(metric);
    REQUIRE(errors.empty());
}

TEST_CASE("MetricValidator rejects invalid host IDs", "[validator]") {
    sentinel::ingestion::MetricValidator validator;
    sentinel::models::Metric metric;
    metric.cpu_percent = 50.0;
    metric.memory_percent = 50.0;
    metric.error_rate = 0.01;

    SECTION("Empty host ID") {
        metric.host_id = "";
        REQUIRE_FALSE(validator.isValid(metric));
        auto errors = validator.validate(metric);
        REQUIRE(errors.size() >= 1);
        CHECK(errors[0].field == "host_id");
    }

    SECTION("Invalid characters in host ID") {
        metric.host_id = "server;DROP TABLE metrics;--";
        REQUIRE_FALSE(validator.isValid(metric));
        auto errors = validator.validate(metric);
        REQUIRE(errors.size() >= 1);
        CHECK(errors[0].field == "host_id");
    }
}

TEST_CASE("MetricValidator catches out of range metrics", "[validator]") {
    sentinel::ingestion::MetricValidator validator;
    sentinel::models::Metric metric;
    metric.host_id = "server-01";

    SECTION("CPU out of range") {
        metric.cpu_percent = 105.0;
        metric.memory_percent = 50.0;
        metric.error_rate = 0.0;
        REQUIRE_FALSE(validator.isValid(metric));
    }

    SECTION("Error rate out of bounds") {
        metric.cpu_percent = 50.0;
        metric.memory_percent = 50.0;
        metric.error_rate = 1.5;
        REQUIRE_FALSE(validator.isValid(metric));
    }

    SECTION("Negative latency") {
        metric.cpu_percent = 50.0;
        metric.memory_percent = 50.0;
        metric.error_rate = 0.01;
        metric.request_latency_ms = -10.0;
        REQUIRE_FALSE(validator.isValid(metric));
    }
}
