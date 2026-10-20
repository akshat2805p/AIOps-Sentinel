"""
prepare_data.py
---------------
Loads the raw labeled telemetry CSV, validates columns, handles
missing values, and performs a chronological train/val/test split.

Key design choices:
  - Time-based split (no random shuffle) to prevent data leakage.
  - Normalization parameters are fit ONLY on the training portion.
  - Saves the processed features and split indices for reproducibility.
"""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.preprocessing import StandardScaler
import joblib


def load_config(path: str = "ml/configs/training.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def validate_dataframe(df: pd.DataFrame, expected_cols: list) -> None:
    """Check that every expected column is present."""
    missing = set(expected_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in dataset: {missing}")

    # Check for entirely empty columns
    for col in expected_cols:
        if df[col].isna().all():
            raise ValueError(f"Column '{col}' is completely empty")


def chronological_split(df: pd.DataFrame, train_ratio: float,
                        val_ratio: float):
    """
    Split by timestamp — no shuffling.  This is critical because
    shuffling time-series data causes future information to leak
    into the training set.
    """
    df = df.sort_values("timestamp").reset_index(drop=True)
    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_df = df.iloc[:train_end].copy()
    val_df = df.iloc[train_end:val_end].copy()
    test_df = df.iloc[val_end:].copy()

    return train_df, val_df, test_df


def main():
    parser = argparse.ArgumentParser(description="Prepare telemetry data")
    parser.add_argument("--config", default="ml/configs/training.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    data_cfg = cfg["data"]
    feat_cfg = cfg["features"]
    out_cfg = cfg["output"]

    raw_path = data_cfg["raw_path"]
    print(f"Loading raw data from {raw_path} ...")
    df = pd.read_csv(raw_path, parse_dates=["timestamp"])

    metric_cols = feat_cfg["raw_metrics"]
    validate_dataframe(df, ["timestamp", "host_id"] + metric_cols)

    # Handle missing values — forward fill within each host, then drop
    # any remaining nulls (only at the very start of a host's series)
    df.sort_values(["host_id", "timestamp"], inplace=True)
    for col in metric_cols:
        df[col] = df.groupby("host_id")[col].transform(
            lambda s: s.fillna(method="ffill")
        )
    before = len(df)
    df.dropna(subset=metric_cols, inplace=True)
    dropped = before - len(df)
    if dropped > 0:
        print(f"  Dropped {dropped} rows with remaining NaN values")

    # ----- Chronological split -----
    train_df, val_df, test_df = chronological_split(
        df,
        data_cfg["train_ratio"],
        data_cfg["val_ratio"]
    )
    print(f"  Split sizes — train: {len(train_df)}, val: {len(val_df)}, "
          f"test: {len(test_df)}")

    # ----- Fit scaler on training data only -----
    scaler = StandardScaler()
    scaler.fit(train_df[metric_cols])

    # Transform all splits
    for split_df in [train_df, val_df, test_df]:
        scaled = scaler.transform(split_df[metric_cols])
        for i, col in enumerate(metric_cols):
            split_df[f"{col}_scaled"] = scaled[:, i]

    # Save outputs
    processed_dir = Path(data_cfg["processed_path"]).parent
    processed_dir.mkdir(parents=True, exist_ok=True)

    train_df.to_csv(processed_dir / "train.csv", index=False)
    val_df.to_csv(processed_dir / "val.csv", index=False)
    test_df.to_csv(processed_dir / "test.csv", index=False)

    # Save the scaler for inference
    model_dir = Path(out_cfg["model_dir"])
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, out_cfg["scaler_path"])

    # Save split metadata for reproducibility
    split_info = {
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
        "train_time_range": [
            str(train_df["timestamp"].min()),
            str(train_df["timestamp"].max())
        ],
        "val_time_range": [
            str(val_df["timestamp"].min()),
            str(val_df["timestamp"].max())
        ],
        "test_time_range": [
            str(test_df["timestamp"].min()),
            str(test_df["timestamp"].max())
        ],
        "feature_means": dict(zip(metric_cols, scaler.mean_.tolist())),
        "feature_stds": dict(zip(metric_cols, scaler.scale_.tolist())),
        "anomaly_counts": {
            "train": int(train_df["is_anomaly"].sum()),
            "val": int(val_df["is_anomaly"].sum()),
            "test": int(test_df["is_anomaly"].sum())
        }
    }
    with open(processed_dir / "split_info.json", "w") as f:
        json.dump(split_info, f, indent=2)

    print(f"\n  Saved processed splits to {processed_dir}/")
    print(f"  Saved scaler to {out_cfg['scaler_path']}")
    print("  Done.")


if __name__ == "__main__":
    main()
