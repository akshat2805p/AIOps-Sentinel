/**
 * metrics_controller.cpp — Telemetry ingestion and retrieval endpoints
 */

#include <drogon/HttpController.h>
#include <drogon/drogon.h>
#include "sentinel/models/metric.hpp"
#include "sentinel/ingestion/metric_validator.hpp"
#include "sentinel/storage/metrics_repository.hpp"
#include "sentinel/inference/model_runner.hpp"
#include "sentinel/alerts/alert_engine.hpp"

namespace sentinel::api {

class MetricsController : public drogon::HttpController<MetricsController> {
public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(MetricsController::ingestMetric, "/api/v1/metrics", drogon::Post, drogon::Options);
    ADD_METHOD_TO(MetricsController::getMetrics, "/api/v1/metrics", drogon::Get, drogon::Options);
    ADD_METHOD_TO(MetricsController::getHosts, "/api/v1/hosts", drogon::Get, drogon::Options);
    METHOD_LIST_END

    MetricsController() {
        repo_ = std::make_unique<sentinel::storage::MetricsRepository>();
        validator_ = std::make_unique<sentinel::ingestion::MetricValidator>();
        model_runner_ = std::make_unique<sentinel::inference::ModelRunner>();
        alert_engine_ = std::make_unique<sentinel::alerts::AlertEngine>();

        // Load models
        model_runner_->loadModel("ml/models/isolation_forest.onnx", "ml/models/scaler.joblib");
    }

    void ingestMetric(const drogon::HttpRequestPtr& req,
                      std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
        auto json_opt = req->getJsonObject();
        if (!json_opt) {
            Json::Value err;
            err["error"] = "Invalid JSON in request body";
            auto resp = drogon::HttpResponse::newHttpJsonResponse(err);
            resp->setStatusCode(drogon::k400BadRequest);
            callback(resp);
            return;
        }

        auto metric_opt = sentinel::models::Metric::fromJson(*json_opt);
        if (!metric_opt) {
            Json::Value err;
            err["error"] = "Missing required fields in metric payload (host_id, metrics)";
            auto resp = drogon::HttpResponse::newHttpJsonResponse(err);
            resp->setStatusCode(drogon::k400BadRequest);
            callback(resp);
            return;
        }

        auto metric = *metric_opt;
        auto errors = validator_->validate(metric);
        if (!errors.empty()) {
            Json::Value err;
            err["error"] = "Validation failed";
            Json::Value err_list(Json::arrayValue);
            for (const auto& e : errors) {
                Json::Value item;
                item["field"] = e.field;
                item["message"] = e.message;
                err_list.append(item);
            }
            err["details"] = err_list;
            auto resp = drogon::HttpResponse::newHttpJsonResponse(err);
            resp->setStatusCode(drogon::k422UnprocessableEntity);
            callback(resp);
            return;
        }

        // Run Anomaly Inference
        auto anomaly_res = model_runner_->score(metric);
        bool alert_triggered = alert_engine_->shouldAlert(metric.host_id, anomaly_res);

        // Upsert host record
        repo_->upsertHost(metric.host_id, metric.host_id, [](bool) {});

        // Save metric to DB
        repo_->insertMetric(metric, [this, metric, anomaly_res, alert_triggered, callback](bool success, int64_t id) {
            if (!success) {
                Json::Value err;
                err["error"] = "Database persistence failed";
                auto resp = drogon::HttpResponse::newHttpJsonResponse(err);
                resp->setStatusCode(drogon::k500InternalServerError);
                callback(resp);
                return;
            }

            if (alert_triggered) {
                sentinel::models::Alert alert;
                alert.host_id = metric.host_id;
                alert.detected_at = std::chrono::system_clock::now();
                alert.anomaly_score = anomaly_res.anomaly_score;
                alert.severity = anomaly_res.severity;
                alert.model_version = anomaly_res.model_version;
                alert.evidence = metric.toJson();

                this->repo_->insertAlert(alert, [](bool, int64_t) {});
            }

            Json::Value response;
            response["status"] = "accepted";
            response["metric_id"] = static_cast<Json::Int64>(id);
            response["host_id"] = metric.host_id;
            response["anomaly_score"] = anomaly_res.anomaly_score;
            response["is_anomaly"] = anomaly_res.is_anomaly;
            response["severity"] = anomaly_res.severity;
            response["model_version"] = anomaly_res.model_version;
            response["alert_triggered"] = alert_triggered;

            auto resp = drogon::HttpResponse::newHttpJsonResponse(response);
            resp->setStatusCode(drogon::k201Created);
            callback(resp);
        });
    }

    void getMetrics(const drogon::HttpRequestPtr& req,
                    std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
        std::string host_id = req->getParameter("host_id");
        int limit = 100;
        std::string limit_param = req->getParameter("limit");
        if (!limit_param.empty()) {
            try {
                limit = std::stoi(limit_param);
                if (limit < 1) limit = 1;
                if (limit > 1000) limit = 1000;
            } catch (...) {}
        }

        repo_->getLatestMetrics(host_id, limit, [callback](std::vector<sentinel::models::Metric> metrics) {
            Json::Value root;
            Json::Value items(Json::arrayValue);
            for (const auto& m : metrics) {
                items.append(m.toJson());
            }
            root["count"] = static_cast<Json::UInt64>(metrics.size());
            root["metrics"] = items;

            auto resp = drogon::HttpResponse::newHttpJsonResponse(root);
            resp->setStatusCode(drogon::k200OK);
            callback(resp);
        });
    }

    void getHosts(const drogon::HttpRequestPtr& req,
                  std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
        auto db = drogon::app().getDbClient();
        if (!db) {
            Json::Value err;
            err["error"] = "Database unavailable";
            auto resp = drogon::HttpResponse::newHttpJsonResponse(err);
            resp->setStatusCode(drogon::k500InternalServerError);
            callback(resp);
            return;
        }

        db->execSqlAsync(
            "SELECT host_id, hostname, registered_at, last_seen_at FROM hosts ORDER BY last_seen_at DESC",
            [callback](const drogon::orm::Result& result) {
                Json::Value root;
                Json::Value hosts(Json::arrayValue);
                for (const auto& row : result) {
                    Json::Value h;
                    h["host_id"] = row["host_id"].as<std::string>();
                    h["hostname"] = row["hostname"].as<std::string>();
                    h["last_seen_at"] = row["last_seen_at"].as<std::string>();
                    hosts.append(h);
                }
                root["hosts"] = hosts;
                auto resp = drogon::HttpResponse::newHttpJsonResponse(root);
                callback(resp);
            },
            [callback](const drogon::orm::DrogonDbException& e) {
                Json::Value err;
                err["error"] = e.base().what();
                auto resp = drogon::HttpResponse::newHttpJsonResponse(err);
                resp->setStatusCode(drogon::k500InternalServerError);
                callback(resp);
            }
        );
    }

private:
    std::unique_ptr<sentinel::storage::MetricsRepository> repo_;
    std::unique_ptr<sentinel::ingestion::MetricValidator> validator_;
    std::unique_ptr<sentinel::inference::ModelRunner> model_runner_;
    std::unique_ptr<sentinel::alerts::AlertEngine> alert_engine_;
};

}  // namespace sentinel::api
