#include <catch2/catch_test_macros.hpp>
#include "sentinel/alerts/alert_engine.hpp"

TEST_CASE("AlertEngine consecutive count behavior", "[alerts]") {
    sentinel::alerts::AlertConfig config;
    config.min_consecutive = 2;
    config.cooldown_seconds = 10;
    sentinel::alerts::AlertEngine engine(config);

    sentinel::models::AnomalyResult anomaly;
    anomaly.is_anomaly = true;
    anomaly.anomaly_score = -0.25;

    sentinel::models::AnomalyResult normal;
    normal.is_anomaly = false;
    normal.anomaly_score = 0.05;

    SECTION("Single anomaly does not alert when min_consecutive is 2") {
        CHECK_FALSE(engine.shouldAlert("host-1", anomaly));
        CHECK(engine.getConsecutiveCount("host-1") == 1);
    }

    SECTION("Second consecutive anomaly triggers alert") {
        CHECK_FALSE(engine.shouldAlert("host-1", anomaly));
        CHECK(engine.shouldAlert("host-1", anomaly));
        CHECK(engine.getConsecutiveCount("host-1") == 2);
    }

    SECTION("Normal observation resets consecutive count") {
        CHECK_FALSE(engine.shouldAlert("host-1", anomaly));
        CHECK(engine.getConsecutiveCount("host-1") == 1);
        CHECK_FALSE(engine.shouldAlert("host-1", normal));
        CHECK(engine.getConsecutiveCount("host-1") == 0);
    }
}

TEST_CASE("AlertEngine severity classification", "[alerts]") {
    sentinel::alerts::AlertEngine engine;

    CHECK(engine.classifySeverity(-0.40) == "critical");
    CHECK(engine.classifySeverity(-0.20) == "warning");
    CHECK(engine.classifySeverity(-0.10) == "info");
    CHECK(engine.classifySeverity(0.05) == "normal");
}
