cmake_minimum_required(VERSION 3.16)
project(sentinel_backend
    VERSION 1.0.0
    LANGUAGES CXX
    DESCRIPTION "AIOps Sentinel C++ backend with Drogon"
)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ─── Dependencies ───
find_package(Drogon CONFIG REQUIRED)
find_package(PostgreSQL REQUIRED)

# ONNX Runtime (optional — for native ML inference)
find_package(onnxruntime QUIET)
if(onnxruntime_FOUND)
    message(STATUS "ONNX Runtime found — native inference enabled")
    add_compile_definitions(HAS_ONNX_RUNTIME)
else()
    message(STATUS "ONNX Runtime not found — using Python bridge for inference")
endif()

# ─── Source files ───
set(SENTINEL_SOURCES
    src/main.cpp
    src/api/metrics_controller.cpp
    src/api/alerts_controller.cpp
    src/api/health_controller.cpp
    src/ingestion/metric_validator.cpp
    src/storage/metrics_repository.cpp
    src/inference/model_runner.cpp
    src/alerts/alert_engine.cpp
)

# ─── Main executable ───
add_executable(sentinel_backend ${SENTINEL_SOURCES})

target_include_directories(sentinel_backend PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_link_libraries(sentinel_backend PRIVATE
    Drogon::Drogon
    PostgreSQL::PostgreSQL
)

if(onnxruntime_FOUND)
    target_link_libraries(sentinel_backend PRIVATE onnxruntime::onnxruntime)
endif()

# ─── Tests ───
option(BUILD_TESTS "Build unit tests" ON)
if(BUILD_TESTS)
    find_package(Catch2 3 QUIET)
    if(Catch2_FOUND)
        enable_testing()
        add_executable(sentinel_tests
            tests/unit/test_validator.cpp
            tests/unit/test_alert_engine.cpp
            src/ingestion/metric_validator.cpp
            src/alerts/alert_engine.cpp
        )
        target_include_directories(sentinel_tests PRIVATE
            ${CMAKE_CURRENT_SOURCE_DIR}/include
        )
        target_link_libraries(sentinel_tests PRIVATE Catch2::Catch2WithMain)
        include(CTest)
        include(Catch)
        catch_discover_tests(sentinel_tests)
    else()
        message(STATUS "Catch2 not found — skipping tests")
    endif()
endif()

# ─── Install ───
install(TARGETS sentinel_backend DESTINATION bin)
