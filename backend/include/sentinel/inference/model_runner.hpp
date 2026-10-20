#pragma once
/**
 * model_runner.hpp — ML model inference interface
 *
 * Supports two backends:
 *   1. ONNX Runtime: loads the exported .onnx model for native C++ inference
 *   2. Python bridge: calls the Python predict module via subprocess
 *
 * The ONNX path is preferred for production; the Python bridge is a
 * fallback during development.
 */

#include <string>
#include <vector>
#include "sentinel/models/metric.hpp"

#ifdef HAS_ONNX_RUNTIME
#include <onnxruntime_cxx_api.h>
#endif

namespace sentinel::inference {

class ModelRunner {
public:
    ModelRunner();
    ~ModelRunner();

    /**
     * Load the model from disk.  Tries ONNX first, then Python bridge.
     */
    bool loadModel(const std::string& model_path,
                   const std::string& scaler_path);

    /**
     * Score a single metric observation.
     */
    sentinel::models::AnomalyResult score(
        const sentinel::models::Metric& metric);

    /**
     * Check whether the model is loaded and ready.
     */
    bool isReady() const { return is_loaded_; }

    std::string getModelVersion() const { return model_version_; }

private:
    bool is_loaded_{false};
    std::string model_version_{"not-loaded"};
    double threshold_{-0.15};

    // Feature scaling parameters (from sklearn StandardScaler)
    std::vector<double> scaler_means_;
    std::vector<double> scaler_scales_;
    std::vector<std::string> feature_names_;

#ifdef HAS_ONNX_RUNTIME
    Ort::Env ort_env_;
    std::unique_ptr<Ort::Session> ort_session_;
    Ort::MemoryInfo memory_info_;
    bool useOnnxInference(const std::vector<float>& features,
                          double& score);
#endif

    /**
     * Fallback: call Python subprocess for inference.
     */
    sentinel::models::AnomalyResult pythonBridgeScore(
        const sentinel::models::Metric& metric);

    /**
     * Build the raw feature vector from a Metric struct.
     */
    std::vector<float> buildFeatureVector(
        const sentinel::models::Metric& metric);
};

}  // namespace sentinel::inference
