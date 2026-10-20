/**
 * alerts_controller.cpp — Incident and alert endpoints for Drogon
 */

#include <drogon/HttpController.h>
#include <drogon/drogon.h>
#include "sentinel/storage/metrics_repository.hpp"

namespace sentinel::api {

class AlertsController : public drogon::HttpController<AlertsController> {
public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(AlertsController::getAlerts, "/api/v1/alerts", drogon::Get, drogon::Options);
    ADD_METHOD_TO(AlertsController::getAnomalies, "/api/v1/anomalies", drogon::Get, drogon::Options);
    ADD_METHOD_TO(AlertsController::acknowledgeAlert, "/api/v1/alerts/{id}/ack", drogon::Post, drogon::Put, drogon::Options);
    METHOD_LIST_END

    AlertsController() {
        repo_ = std::make_unique<sentinel::storage::MetricsRepository>();
    }

    void getAlerts(const drogon::HttpRequestPtr& req,
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

        std::string host_id = req->getParameter("host_id");
        std::string status = req->getParameter("status");
        std::string severity = req->getParameter("severity");
        int limit = 100;
        std::string limit_param = req->getParameter("limit");
        if (!limit_param.empty()) {
            try { limit = std::clamp(std::stoi(limit_param), 1, 1000); } catch (...) {}
        }

        std::string query = "SELECT id, host_id, detected_at, anomaly_score, severity, status, model_version, evidence, acknowledged_at, acknowledged_by FROM alerts WHERE 1=1";
        std::vector<std::string> params;

        if (!host_id.empty()) {
            query += " AND host_id = $" + std::to_string(params.size() + 1);
            params.push_back(host_id);
        }
        if (!status.empty()) {
            query += " AND status = $" + std::to_string(params.size() + 1);
            params.push_back(status);
        }
        if (!severity.empty()) {
            query += " AND severity = $" + std::to_string(params.size() + 1);
            params.push_back(severity);
        }

        query += " ORDER BY detected_at DESC LIMIT " + std::to_string(limit);

        // Execute query
        db->execSqlAsync(
            query,
            [callback](const drogon::orm::Result& result) {
                Json::Value root;
                Json::Value alerts(Json::arrayValue);
                for (const auto& row : result) {
                    Json::Value item;
                    item["id"] = row["id"].as<int64_t>();
                    item["host_id"] = row["host_id"].as<std::string>();
                    item["detected_at"] = row["detected_at"].as<std::string>();
                    item["anomaly_score"] = row["anomaly_score"].as<double>();
                    item["severity"] = row["severity"].as<std::string>();
                    item["status"] = row["status"].as<std::string>();
                    item["model_version"] = row["model_version"].as<std::string>();
                    alerts.append(item);
                }
                root["count"] = static_cast<Json::UInt64>(alerts.size());
                root["alerts"] = alerts;
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

    void getAnomalies(const drogon::HttpRequestPtr& req,
                      std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
        // Alias for alerts with detected anomalies
        getAlerts(req, std::move(callback));
    }

    void acknowledgeAlert(const drogon::HttpRequestPtr& req,
                          std::function<void(const drogon::HttpResponsePtr&)>&& callback,
                          int64_t id) {
        std::string ack_by = "operator";
        auto json = req->getJsonObject();
        if (json && json->isMember("acknowledged_by")) {
            ack_by = (*json)["acknowledged_by"].asString();
        }

        repo_->acknowledgeAlert(id, ack_by, [callback, id](bool success) {
            Json::Value res;
            if (success) {
                res["status"] = "acknowledged";
                res["alert_id"] = static_cast<Json::Int64>(id);
                auto resp = drogon::HttpResponse::newHttpJsonResponse(res);
                callback(resp);
            } else {
                res["error"] = "Alert not found or already acknowledged";
                auto resp = drogon::HttpResponse::newHttpJsonResponse(res);
                resp->setStatusCode(drogon::k404NotFound);
                callback(resp);
            }
        });
    }

private:
    std::unique_ptr<sentinel::storage::MetricsRepository> repo_;
};

}  // namespace sentinel::api
