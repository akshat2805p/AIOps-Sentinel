"""
predict.py
----------
Loads a trained model and runs inference on new metric observations.

Two modes:
  1. Batch: score a CSV file of metrics
  2. Single: score a single JSON observation (used by the backend)

This module is also imported by the C++ backend's Python bridge
or called as a subprocess for model inference.
"""

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml


def load_config(path: str = "ml/configs/training.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


class AnomalyPredictor:
    """
    Wraps the trained Isolation Forest model, scaler, and feature
    engineering pipeline into a single prediction interface.
    """

    def __init__(self, config_path: str = "ml/configs/training.yaml"):
        cfg = load_config(config_path)
        out_cfg = cfg["output"]
        self.feat_cfg = cfg["features"]

        # Load model
        artifact = joblib.load(out_cfg["forest_path"])
        self.model = artifact["model"]
        self.threshold = artifact["threshold"]
        self.feature_columns = artifact["feature_columns"]
        self.model_version = artifact.get("model_version", "unknown")

        # Load scaler
        self.scaler = joblib.load(out_cfg["scaler_path"])
        self.metric_cols = self.feat_cfg["raw_metrics"]

        # Try loading risk model (optional)
        self.risk_model = None
        risk_path = Path(out_cfg["risk_model_path"])
        if risk_path.exists():
            risk_artifact = joblib.load(risk_path)
            self.risk_model = risk_artifact["model"]

    def _prepare_single(self, metrics: dict) -> np.ndarray:
        """
        Build a feature vector from a single metric observation.
        For single-point inference, rolling stats default to the
        raw value (window of 1) and diffs default to 0.
        """
        raw_values = [metrics.get(col, 0.0) for col in self.metric_cols]
        raw_array = np.array([raw_values])
        scaled = self.scaler.transform(raw_array)[0]

        # Build the full feature vector
        features = {}
        for i, col in enumerate(self.metric_cols):
            features[f"{col}_scaled"] = scaled[i]

        # Rolling features default to scaled value (single observation)
        for w in self.feat_cfg.get("rolling_windows", []):
            for stat in self.feat_cfg.get("rolling_stats", []):
                for col in self.metric_cols:
                    if stat == "mean":
                        features[f"{col}_roll{w}_{stat}"] = features[f"{col}_scaled"]
                    else:
                        features[f"{col}_roll{w}_{stat}"] = 0.0

        # Diff features default to 0 (no history)
        for lag in self.feat_cfg.get("diff_lags", []):
            for col in self.metric_cols:
                features[f"{col}_diff{lag}"] = 0.0

        # Assemble in the correct column order
        vector = [features.get(col, 0.0) for col in self.feature_columns]
        return np.array([vector])

    def predict_single(self, metrics: dict) -> dict:
        """
        Score a single observation.
        Returns anomaly score, is_anomaly flag, and severity.
        """
        features = self._prepare_single(metrics)
        score = float(self.model.decision_function(features)[0])
        is_anomaly = score < self.threshold

        # Determine severity based on score
        if score < -0.35:
            severity = "critical"
        elif score < -0.15:
            severity = "warning"
        elif score < -0.05:
            severity = "info"
        else:
            severity = "normal"

        result = {
            "anomaly_score": round(score, 6),
            "is_anomaly": bool(is_anomaly),
            "severity": severity,
            "model_version": self.model_version,
            "threshold": self.threshold
        }

        # Optional risk prediction
        if self.risk_model is not None:
            risk_prob = float(
                self.risk_model.predict_proba(features)[0][1]
            )
            result["risk_probability"] = round(risk_prob, 4)
            result["risk_level"] = (
                "high" if risk_prob > 0.7
                else "medium" if risk_prob > 0.3
                else "low"
            )

        return result

    def predict_batch(self, csv_path: str) -> pd.DataFrame:
        """Score every row in a CSV file."""
        df = pd.read_csv(csv_path)
        results = []
        for _, row in df.iterrows():
            metrics = {col: row[col] for col in self.metric_cols
                       if col in row}
            pred = self.predict_single(metrics)
            results.append(pred)
        return pd.DataFrame(results)


def main():
    parser = argparse.ArgumentParser(description="Run anomaly prediction")
    parser.add_argument("--config", default="ml/configs/training.yaml")
    parser.add_argument("--input-csv", default=None,
                        help="CSV file to batch-score")
    parser.add_argument("--input-json", default=None,
                        help="JSON string for single observation")
    args = parser.parse_args()

    predictor = AnomalyPredictor(args.config)

    if args.input_json:
        metrics = json.loads(args.input_json)
        result = predictor.predict_single(metrics)
        print(json.dumps(result, indent=2))

    elif args.input_csv:
        results_df = predictor.predict_batch(args.input_csv)
        print(results_df.to_string())
        output_path = args.input_csv.replace(".csv", "_scored.csv")
        results_df.to_csv(output_path, index=False)
        print(f"\nSaved scored results to {output_path}")

    else:
        # Demo mode — score a sample observation
        sample = {
            "cpu_percent": 92.4,
            "memory_percent": 84.1,
            "disk_io_bytes_sec": 1400000,
            "network_bytes_sec": 850000,
            "request_latency_ms": 240,
            "error_rate": 0.025
        }
        print("Scoring sample observation:")
        print(json.dumps(sample, indent=2))
        result = predictor.predict_single(sample)
        print("\nPrediction result:")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
