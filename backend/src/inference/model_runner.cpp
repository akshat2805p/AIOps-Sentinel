/**
 * model_runner.cpp — ML model inference implementation
 *
 * Implements the ModelRunner class with ONNX Runtime and Python bridge backends.
 */

#include "sentinel/inference/model_runner.hpp"
#include <iostream>
#include <sstream>
#include <fstream>
#include <array>
#include <memory>
#include <cstdio>
#include <cmath>

namespace sentinel::inference {

ModelRunner::ModelRunner() {
#ifdef HAS_ONNX_RUNTIME
    ort_env_ = Ort::Env(ORT_LOGGING_LEVEL_WARNING, "SentinelModelRunner");
    memory_info_ = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
#endif
}

ModelRunner::~ModelRunner() = default;

bool ModelRunner::loadModel(const std::string& model_path,
                           const std::string& scaler_path) {
#ifdef HAS_ONNX_RUNTIME
    try {
        Ort::SessionOptions session_options;
        session_options.SetIntraOpNumThreads(1);
        session_options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);

#if defined(_WIN32)
        std::wstring w_path(model_path.begin(), model_path.end());
        ort_session_ = std::make_unique<Ort::Session>(ort_env_, w_path.c_str(), session_options);
#else
        ort_session_ = std::make_unique<Ort::Session>(ort_env_, model_path.c_str(), session_options);
#endif

        is_loaded_ = true;
        model_version_ = "onnx-v1.0";
        std::cout << "[ModelRunner] Loaded ONNX model successfully from: " << model_path << std::endl;
        return true;
    } catch (const std::exception& e) {
        std::cerr << "[ModelRunner] Failed to load ONNX model: " << e.what()
                  << ". Falling back to Python bridge." << std::endl;
    }
#endif

    // Fallback or development mode using Python bridge
    std::ifstream check_model(model_path);
    if (check_model.good()) {
        is_loaded_ = true;
        model_version_ = "iforest-v1.0";
        std::cout << "[ModelRunner] Verified model path for Python bridge: " << model_path << std::endl;
        return true;
    }

    // Even if specific model files are pending, ready fallback heuristic scorer
    is_loaded_ = true;
    model_version_ = "heuristic-v1.0";
    std::cout << "[ModelRunner] Initialized with heuristic anomaly detection baseline." << std::endl;
    return true;
}

std::vector<float> ModelRunner::buildFeatureVector(
    const sentinel::models::Metric& metric) {
    // Basic 6-feature raw vector: cpu, memory, disk_io, net_io, latency, error_rate
    std::vector<float> vec = {
        static_cast<float>(metric.cpu_percent),
        static_cast<float>(metric.memory_percent),
        static_cast<float>(metric.disk_io_bytes_sec),
        static_cast<float>(metric.network_bytes_sec),
        static_cast<float>(metric.request_latency_ms),
        static_cast<float>(metric.error_rate)
    };
    return vec;
}

#ifdef HAS_ONNX_RUNTIME
bool ModelRunner::useOnnxInference(const std::vector<float>& features, double& score) {
    if (!ort_session_) return false;
    try {
        std::array<int64_t, 2> input_shape = {1, static_cast<int64_t>(features.size())};
        Ort::Value input_tensor = Ort::Value::CreateTensor<float>(
            memory_info_, const_cast<float*>(features.data()), features.size(),
            input_shape.data(), input_shape.size());

        const char* input_names[] = {"input"};
        const char* output_names[] = {"score"};

        auto output_tensors = ort_session_->Run(
            Ort::RunOptions{nullptr},
            input_names, &input_tensor, 1,
            output_names, 1);

        if (!output_tensors.empty() && output_tensors.front().IsTensor()) {
            float* out_data = output_tensors.front().GetTensorMutableData<float>();
            score = static_cast<double>(out_data[0]);
            return true;
        }
    } catch (const std::exception& e) {
        std::cerr << "[ModelRunner] ONNX inference error: " << e.what() << std::endl;
    }
    return false;
}
#endif

sentinel::models::AnomalyResult ModelRunner::pythonBridgeScore(
    const sentinel::models::Metric& metric) {

    // Format metric as JSON string
    std::ostringstream json_ss;
    json_ss << "{\"cpu_percent\":" << metric.cpu_percent
            << ",\"memory_percent\":" << metric.memory_percent
            << ",\"disk_io_bytes_sec\":" << metric.disk_io_bytes_sec
            << ",\"network_bytes_sec\":" << metric.network_bytes_sec
            << ",\"request_latency_ms\":" << metric.request_latency_ms
            << ",\"error_rate\":" << metric.error_rate << "}";

    std::string json_payload = json_ss.str();

    // Call python -m ml.src.predict --input-json '<json>'
#if defined(_WIN32)
    std::string cmd = "python -m ml.src.predict --input-json \"" + json_payload + "\" 2>nul";
#else
    std::string cmd = "python3 -m ml.src.predict --input-json '" + json_payload + "' 2>/dev/null";
#endif

    std::array<char, 256> buffer;
    std::string result_str;
    std::unique_ptr<FILE, decltype(&fclose)> pipe(
#if defined(_WIN32)
        _popen(cmd.c_str(), "r"), _pclose
#else
        popen(cmd.c_str(), "r"), pclose
#endif
    );

    if (pipe) {
        while (fgets(buffer.data(), buffer.size(), pipe.get()) != nullptr) {
            result_str += buffer.data();
        }
    }

    sentinel::models::AnomalyResult res;
    res.model_version = model_version_;

    // Attempt to parse JSON response from Python
    if (!result_str.empty()) {
        try {
            Json::CharReaderBuilder builder;
            std::unique_ptr<Json::CharReader> reader(builder.newCharReader());
            Json::Value root;
            std::string errs;
            std::istringstream s(result_str);
            if (reader->parse(result_str.data(), result_str.data() + result_str.size(), &root, &errs)) {
                if (root.isMember("anomaly_score")) {
                    res.anomaly_score = root["anomaly_score"].asDouble();
                    res.is_anomaly = root["is_anomaly"].asBool();
                    res.severity = root["severity"].asString();
                    res.model_version = root["model_version"].asString();
                    return res;
                }
            }
        } catch (...) {
            // parse failure fallback to statistical model below
        }
    }

    // Built-in Statistical Z-Score fallback when python subprocess is not present:
    // Calculates multidimensional distance from standard operating baseline
    double z_cpu = std::max(0.0, (metric.cpu_percent - 50.0) / 20.0);
    double z_mem = std::max(0.0, (metric.memory_percent - 55.0) / 20.0);
    double z_lat = std::max(0.0, (metric.request_latency_ms - 80.0) / 50.0);
    double z_err = std::max(0.0, (metric.error_rate - 0.01) / 0.02);

    double anomaly_magnitude = (z_cpu * 0.35) + (z_mem * 0.25) + (z_lat * 0.25) + (z_err * 0.35);
    // Transform to standard Isolation Forest style score: normal is ~ 0.0 to 0.2, anomaly is < -0.15
    res.anomaly_score = 0.10 - (anomaly_magnitude * 0.25);
    res.is_anomaly = (res.anomaly_score < threshold_);

    if (res.anomaly_score < -0.35) {
        res.severity = "critical";
    } else if (res.anomaly_score < -0.15) {
        res.severity = "warning";
    } else if (res.anomaly_score < -0.05) {
        res.severity = "info";
    } else {
        res.severity = "normal";
    }

    return res;
}

sentinel::models::AnomalyResult ModelRunner::score(
    const sentinel::models::Metric& metric) {

#ifdef HAS_ONNX_RUNTIME
    if (ort_session_) {
        std::vector<float> features = buildFeatureVector(metric);
        double onnx_score = 0.0;
        if (useOnnxInference(features, onnx_score)) {
            sentinel::models::AnomalyResult res;
            res.anomaly_score = onnx_score;
            res.is_anomaly = (onnx_score < threshold_);
            res.model_version = model_version_;
            if (onnx_score < -0.35) {
                res.severity = "critical";
            } else if (onnx_score < -0.15) {
                res.severity = "warning";
            } else if (onnx_score < -0.05) {
                res.severity = "info";
            } else {
                res.severity = "normal";
            }
            return res;
        }
    }
#endif

    return pythonBridgeScore(metric);
}

}  // namespace sentinel::inference
