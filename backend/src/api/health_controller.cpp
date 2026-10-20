/**
 * health_controller.cpp — Health check and readiness endpoints for Drogon
 */

#include <drogon/HttpController.h>
#include <drogon/drogon.h>
#include <chrono>

namespace sentinel::api {

class HealthController : public drogon::HttpController<HealthController> {
public:
    METHOD_LIST_BEGIN
    ADD_METHOD_TO(HealthController::getHealth, "/health", drogon::Get, drogon::Options);
    ADD_METHOD_TO(HealthController::getHealth, "/api/v1/health", drogon::Get, drogon::Options);
    METHOD_LIST_END

    void getHealth(const drogon::HttpRequestPtr& req,
                   std::function<void(const drogon::HttpResponsePtr&)>&& callback) {
        Json::Value json;
        json["status"] = "healthy";
        json["service"] = "AIOps Sentinel C++ Backend";
        json["version"] = "1.0.0";

        auto now = std::chrono::system_clock::now();
        auto time_t = std::chrono::system_clock::to_time_t(now);
        char buf[64];
        std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", std::gmtime(&time_t));
        json["timestamp"] = buf;

        auto client = drogon::app().getDbClient();
        json["database"] = client ? "connected" : "disconnected";

        auto resp = drogon::HttpResponse::newHttpJsonResponse(json);
        resp->setStatusCode(drogon::k200OK);
        callback(resp);
    }
};

}  // namespace sentinel::api
