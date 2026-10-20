"""
train_risk.py
-------------
Optional supervised incident-risk predictor.

If we have incident labels (from the incidents table or synthetic
injection), we can train a binary classifier:

  Target: will an incident begin within the next T minutes?

This is fundamentally different from anomaly detection:
  - Anomaly detection says "this observation is unusual"
  - Risk prediction says "an incident is likely soon"

We use a Gradient Boosting classifier and evaluate with
precision, recall, F1, and PR-AUC.

Important: the target label must be constructed BEFORE training
so that no future information leaks into the input features.
"""

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    average_precision_score, classification_report
)


def load_config(path: str = "ml/configs/training.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_feature_columns(df: pd.DataFrame) -> list:
    return [c for c in df.columns
            if c.endswith("_scaled") or "_roll" in c or "_diff" in c]


def create_risk_labels(df: pd.DataFrame,
                       lookahead_minutes: int = 10,
                       interval_seconds: int = 10) -> np.ndarray:
    """
    For each row, check if any anomaly/incident starts within the
    next `lookahead_minutes`.  Label = 1 if yes, 0 if no.

    This uses the is_anomaly column as a proxy for incidents.
    In a real deployment, you would join with the incidents table.
    """
    lookahead_rows = (lookahead_minutes * 60) // interval_seconds
    labels = np.zeros(len(df), dtype=int)

    anomaly_flags = df["is_anomaly"].values

    for i in range(len(df)):
        window_end = min(i + lookahead_rows, len(df))
        # Check if any anomaly starts in the future window
        # We look for a transition from 0 to 1
        window = anomaly_flags[i + 1:window_end]
        if len(window) > 0 and window.any():
            labels[i] = 1

    return labels


def main():
    parser = argparse.ArgumentParser(
        description="Train supervised risk predictor"
    )
    parser.add_argument("--config", default="ml/configs/training.yaml")
    parser.add_argument("--lookahead-minutes", type=int, default=10,
                        help="How far ahead to predict incidents")
    args = parser.parse_args()

    cfg = load_config(args.config)
    gb_cfg = cfg["model"]["gradient_boosting"]
    out_cfg = cfg["output"]
    processed_dir = Path(cfg["data"]["processed_path"]).parent

    print("  Loading windowed training and validation data ...")
    train_df = pd.read_csv(processed_dir / "train_windowed.csv",
                           parse_dates=["timestamp"])
    val_df = pd.read_csv(processed_dir / "val_windowed.csv",
                         parse_dates=["timestamp"])

    feature_cols = get_feature_columns(train_df)
    print(f"  Using {len(feature_cols)} features")

    # Create forward-looking risk labels
    print(f"  Creating risk labels (lookahead = {args.lookahead_minutes} min) ...")
    train_risk_labels = create_risk_labels(
        train_df, args.lookahead_minutes
    )
    val_risk_labels = create_risk_labels(
        val_df, args.lookahead_minutes
    )

    print(f"    Train positives: {train_risk_labels.sum()} / {len(train_risk_labels)}")
    print(f"    Val positives: {val_risk_labels.sum()} / {len(val_risk_labels)}")

    if train_risk_labels.sum() < 10:
        print("\n  WARNING: Very few positive samples. Risk model may not "
              "generalize well.  Consider increasing lookahead or adding "
              "more anomaly scenarios.")

    train_features = train_df[feature_cols].values
    val_features = val_df[feature_cols].values

    # Train gradient boosting classifier
    print("\n  Training Gradient Boosting risk predictor ...")
    t0 = time.time()

    gb_model = GradientBoostingClassifier(
        n_estimators=gb_cfg["n_estimators"],
        max_depth=gb_cfg["max_depth"],
        learning_rate=gb_cfg["learning_rate"],
        random_state=gb_cfg["random_state"],
        subsample=0.8
    )
    gb_model.fit(train_features, train_risk_labels)
    train_time = time.time() - t0
    print(f"    Training took {train_time:.2f} seconds")

    # Evaluate on validation set
    val_preds = gb_model.predict(val_features)
    val_probs = gb_model.predict_proba(val_features)[:, 1]

    precision = precision_score(val_risk_labels, val_preds, zero_division=0)
    recall = recall_score(val_risk_labels, val_preds, zero_division=0)
    f1 = f1_score(val_risk_labels, val_preds, zero_division=0)
    pr_auc = average_precision_score(
        val_risk_labels, val_probs
    ) if val_risk_labels.sum() > 0 else 0.0

    print(f"\n  Validation results:")
    print(f"    Precision: {precision:.4f}")
    print(f"    Recall:    {recall:.4f}")
    print(f"    F1 Score:  {f1:.4f}")
    print(f"    PR-AUC:    {pr_auc:.4f}")

    print("\n  Classification Report:")
    print(classification_report(val_risk_labels, val_preds,
                                target_names=["No Risk", "At Risk"],
                                zero_division=0))

    # Feature importances — useful for the report
    importances = gb_model.feature_importances_
    top_k = 10
    top_indices = np.argsort(importances)[::-1][:top_k]
    print(f"  Top {top_k} feature importances:")
    for idx in top_indices:
        print(f"    {feature_cols[idx]}: {importances[idx]:.4f}")

    # Save model
    model_dir = Path(out_cfg["model_dir"])
    model_dir.mkdir(parents=True, exist_ok=True)

    risk_artifact = {
        "model": gb_model,
        "feature_columns": feature_cols,
        "lookahead_minutes": args.lookahead_minutes,
        "training_samples": len(train_features),
        "train_time_sec": round(train_time, 2),
        "model_version": "risk-gb-v1",
        "val_metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "pr_auc": round(pr_auc, 4)
        }
    }
    joblib.dump(risk_artifact, out_cfg["risk_model_path"])
    print(f"\n  Saved risk model to {out_cfg['risk_model_path']}")


if __name__ == "__main__":
    main()
