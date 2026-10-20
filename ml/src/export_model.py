"""
export_model.py
---------------
Exports the trained Isolation Forest to ONNX format so it can be
loaded by ONNX Runtime in the C++ backend for native inference.

This removes the Python dependency from the inference path,
making the C++ backend self-contained.
"""

import argparse
from pathlib import Path

import joblib
import numpy as np
import yaml

try:
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False
    print("Warning: skl2onnx not installed. ONNX export unavailable.")


def load_config(path: str = "ml/configs/training.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Export model to ONNX")
    parser.add_argument("--config", default="ml/configs/training.yaml")
    args = parser.parse_args()

    if not HAS_ONNX:
        print("Install skl2onnx to export: pip install skl2onnx")
        return

    cfg = load_config(args.config)
    out_cfg = cfg["output"]

    # Load trained model artifact
    artifact = joblib.load(out_cfg["forest_path"])
    model = artifact["model"]
    feature_cols = artifact["feature_columns"]
    n_features = len(feature_cols)

    print(f"  Model has {n_features} input features")

    # Define ONNX input type
    initial_type = [
        ("input", FloatTensorType([None, n_features]))
    ]

    # Convert to ONNX
    onnx_model = convert_sklearn(
        model, initial_types=initial_type,
        target_opset=12
    )

    # Save
    onnx_path = out_cfg["onnx_path"]
    Path(onnx_path).parent.mkdir(parents=True, exist_ok=True)
    with open(onnx_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    print(f"  Exported ONNX model to {onnx_path}")
    print(f"  Model size: {Path(onnx_path).stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
