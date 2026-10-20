"""
normalize.py
-------------
Applies the same StandardScaler transform used during training
so that metrics from the collector match the model's expected input.

Loads scaler parameters from the saved joblib artifact.
"""

import os
from pathlib import Path

import joblib
import numpy as np


class MetricNormalizer:
    """Wraps the trained StandardScaler for runtime metric normalization."""

    METRIC_ORDER = [
        "cpu_percent",
        "memory_percent",
        "disk_io_bytes_sec",
        "network_bytes_sec",
        "request_latency_ms",
        "error_rate"
    ]

    def __init__(self, scaler_path: str = "ml/models/scaler.joblib"):
        if not Path(scaler_path).exists():
            raise FileNotFoundError(
                f"Scaler not found at {scaler_path}. "
                "Run the training pipeline first."
            )
        self.scaler = joblib.load(scaler_path)

    def normalize(self, metrics: dict) -> dict:
        """
        Take a raw metrics dict and return normalized values.
        Keys match the training feature names.
        """
        raw = [metrics.get(col, 0.0) for col in self.METRIC_ORDER]
        scaled = self.scaler.transform([raw])[0]

        result = {}
        for i, col in enumerate(self.METRIC_ORDER):
            result[f"{col}_scaled"] = float(scaled[i])

        return result

    def normalize_batch(self, metrics_list: list) -> list:
        """Normalize a list of metric dictionaries."""
        return [self.normalize(m) for m in metrics_list]


if __name__ == "__main__":
    # Quick test
    normalizer = MetricNormalizer()
    sample = {
        "cpu_percent": 45.0,
        "memory_percent": 60.0,
        "disk_io_bytes_sec": 500000,
        "network_bytes_sec": 750000,
        "request_latency_ms": 50,
        "error_rate": 0.005
    }
    print("Normalized:", normalizer.normalize(sample))
