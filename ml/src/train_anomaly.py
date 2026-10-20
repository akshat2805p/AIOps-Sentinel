"""
train_anomaly.py
----------------
Trains the primary anomaly detection model — an Isolation Forest.

Why Isolation Forest?
  - Unsupervised: does not need labeled anomalies for training.
  - We train on "mostly normal" data so the forest learns the normal
    data distribution.  Outliers get shorter average path lengths.
  - The decision_function returns a signed anomaly score (negative =
    more anomalous).  We calibrate a threshold on the validation set.

We also train a simple threshold-based baseline for comparison.  If
Isolation Forest does not beat a basic z-score approach, we need to
investigate the feature engineering.

Output: ml/models/isolation_forest.joblib
"""

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import IsolationForest


def load_config(path: str = "ml/configs/training.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_feature_columns(df: pd.DataFrame) -> list:
    """Return only the engineered feature columns used for training."""
    return [c for c in df.columns
            if c.endswith("_scaled") or "_roll" in c or "_diff" in c]


def train_threshold_baseline(train_features: np.ndarray,
                             val_features: np.ndarray,
                             val_labels: np.ndarray) -> dict:
    """
    Baseline: flag any observation where any feature exceeds ±3 standard
    deviations from the training mean.  This mimics traditional
    threshold-based monitoring.
    """
    train_mean = train_features.mean(axis=0)
    train_std = train_features.std(axis=0)
    # avoid division by zero
    train_std[train_std < 1e-8] = 1.0

    z_scores = np.abs((val_features - train_mean) / train_std)
    max_z = z_scores.max(axis=1)

    # Try a few thresholds and pick the best F1
    best_f1 = 0
    best_threshold = 3.0
    for threshold in [2.0, 2.5, 3.0, 3.5, 4.0]:
        preds = (max_z > threshold).astype(int)
        tp = np.sum((preds == 1) & (val_labels == 1))
        fp = np.sum((preds == 1) & (val_labels == 0))
        fn = np.sum((preds == 0) & (val_labels == 1))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold

    return {
        "method": "z_score_threshold",
        "threshold": best_threshold,
        "val_f1": round(best_f1, 4),
        "train_mean": train_mean.tolist(),
        "train_std": train_std.tolist()
    }


def calibrate_threshold(model, val_features: np.ndarray,
                        val_labels: np.ndarray) -> float:
    """
    Find the decision_function threshold that maximizes F1 on the
    validation set.  We search over quantiles of the score distribution.
    """
    scores = model.decision_function(val_features)

    best_f1 = 0
    best_thresh = -0.15  # sensible default

    # Search a range of thresholds
    candidates = np.percentile(scores, np.arange(1, 30, 0.5))
    candidates = np.unique(np.round(candidates, 4))

    for thresh in candidates:
        preds = (scores < thresh).astype(int)
        tp = np.sum((preds == 1) & (val_labels == 1))
        fp = np.sum((preds == 1) & (val_labels == 0))
        fn = np.sum((preds == 0) & (val_labels == 1))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0)

        if f1 > best_f1:
            best_f1 = f1
            best_thresh = thresh

    return float(best_thresh)


def main():
    parser = argparse.ArgumentParser(description="Train anomaly detector")
    parser.add_argument("--config", default="ml/configs/training.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    model_cfg = cfg["model"]["isolation_forest"]
    out_cfg = cfg["output"]

    processed_dir = Path(cfg["data"]["processed_path"]).parent

    # Load windowed data
    train_df = pd.read_csv(processed_dir / "train_windowed.csv",
                           parse_dates=["timestamp"])
    val_df = pd.read_csv(processed_dir / "val_windowed.csv",
                         parse_dates=["timestamp"])

    feature_cols = get_feature_columns(train_df)
    print(f"  Using {len(feature_cols)} features for training")

    train_features = train_df[feature_cols].values
    val_features = val_df[feature_cols].values
    val_labels = val_df["is_anomaly"].values

    # ---- Train threshold baseline ----
    print("\n  Training z-score threshold baseline ...")
    baseline = train_threshold_baseline(train_features, val_features,
                                        val_labels)
    print(f"    Baseline val F1: {baseline['val_f1']} "
          f"(threshold={baseline['threshold']})")

    # ---- Train Isolation Forest ----
    print("\n  Training Isolation Forest ...")
    t0 = time.time()

    iso_forest = IsolationForest(
        n_estimators=model_cfg["n_estimators"],
        contamination=model_cfg["contamination"],
        max_samples=model_cfg["max_samples"],
        random_state=model_cfg["random_state"],
        n_jobs=model_cfg["n_jobs"]
    )
    iso_forest.fit(train_features)
    train_time = time.time() - t0
    print(f"    Training took {train_time:.2f} seconds")

    # ---- Calibrate threshold on validation set ----
    print("  Calibrating anomaly threshold on validation data ...")
    threshold = calibrate_threshold(iso_forest, val_features, val_labels)
    print(f"    Optimal threshold: {threshold:.4f}")

    # ---- Save model and metadata ----
    model_dir = Path(out_cfg["model_dir"])
    model_dir.mkdir(parents=True, exist_ok=True)

    model_artifact = {
        "model": iso_forest,
        "threshold": threshold,
        "feature_columns": feature_cols,
        "training_samples": len(train_features),
        "train_time_sec": round(train_time, 2),
        "model_version": "iforest-v1",
        "hyperparameters": model_cfg
    }
    joblib.dump(model_artifact, out_cfg["forest_path"])
    print(f"  Saved model to {out_cfg['forest_path']}")

    # Save baseline for comparison
    baseline_path = model_dir / "baseline_threshold.json"
    with open(baseline_path, "w") as f:
        json.dump(baseline, f, indent=2)
    print(f"  Saved baseline to {baseline_path}")

    # Save feature column list for inference
    with open(model_dir / "feature_columns.json", "w") as f:
        json.dump(feature_cols, f, indent=2)

    print("\n  Anomaly model training complete.")


if __name__ == "__main__":
    main()
