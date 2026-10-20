/**
 * main.cpp — AIOps Sentinel Backend Entry Point
 *
 * Initializes the Drogon HTTP framework, configures database connections,
 * loads the ML model, and starts serving the REST API.
 */

#include <drogon/drogon.h>
#include <iostream>
#include <cstdlib>
#include <string>

int main(int argc, char* argv[]) {
    // Load configuration from environment
    std::string db_host = std::getenv("POSTGRES_HOST") ?: "localhost";
    int db_port = std::atoi(std::getenv("POSTGRES_PORT") ?: "5432");
    std::string db_name = std::getenv("POSTGRES_DB") ?: "sentinel";
    std::string db_user = std::getenv("POSTGRES_USER") ?: "sentinel_user";
    std::string db_pass = std::getenv("POSTGRES_PASSWORD") ?: "changeme";
    int server_port = std::atoi(std::getenv("BACKEND_PORT") ?: "8080");

    std::cout << "╔══════════════════════════════════════════╗\n"
              << "║       AIOps Sentinel Backend v1.0        ║\n"
              << "╚══════════════════════════════════════════╝\n"
              << std::endl;

    // Configure Drogon
    drogon::app()
        .setLogPath("./logs")
        .setLogLevel(trantor::Logger::kInfo)
        .addListener("0.0.0.0", server_port)
        .setThreadNum(4)
        .setDocumentRoot("./static")

        // Configure PostgreSQL connection pool
        .createDbClient(
            "postgresql",       // type
            db_host,            // host
            db_port,            // port
            db_name,            // database name
            db_user,            // user
            db_pass,            // password
            4,                  // connection pool size
            "",                 // socket path (empty for TCP)
            "default",          // client name
            false               // is fast (false = normal)
        )

        // Enable CORS for dashboard
        .registerPreRoutingAdvice(
            [](const drogon::HttpRequestPtr& req,
               drogon::FilterCallback&& stop,
               drogon::FilterChainCallback&& pass) {
                // Allow CORS preflight
                if (req->method() == drogon::Options) {
                    auto resp = drogon::HttpResponse::newHttpResponse();
                    resp->addHeader("Access-Control-Allow-Origin", "*");
                    resp->addHeader("Access-Control-Allow-Methods",
                                    "GET, POST, PUT, DELETE, OPTIONS");
                    resp->addHeader("Access-Control-Allow-Headers",
                                    "Content-Type, Authorization");
                    stop(resp);
                    return;
                }
                pass();
            }
        )

        // Add CORS headers to all responses
        .registerPostHandlingAdvice(
            [](const drogon::HttpRequestPtr& req,
               const drogon::HttpResponsePtr& resp) {
                resp->addHeader("Access-Control-Allow-Origin", "*");
                resp->addHeader("Access-Control-Allow-Methods",
                                "GET, POST, PUT, DELETE, OPTIONS");
                resp->addHeader("Access-Control-Allow-Headers",
                                "Content-Type, Authorization");
            }
        );

    std::cout << "Starting server on port " << server_port << " ..."
              << std::endl;
    std::cout << "Database: " << db_user << "@" << db_host
              << ":" << db_port << "/" << db_name << std::endl;

    drogon::app().run();

    return 0;
}
