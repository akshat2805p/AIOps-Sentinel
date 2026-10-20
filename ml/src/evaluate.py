"""
evaluate.py
-----------
Runs the trained anomaly detector and (optionally) the risk predictor
on the held-out TEST set and produces a comprehensive evaluation report.

Metrics computed:
  - Precision, Recall, F1 Score
  - False Positive Rate (FPR)
  - Detection Delay: average time between anomaly onset and first detection
  - Inference Latency: time to score the full test set
  - Confusion matrix
  - Comparison with the z-score threshold baseline

All results are saved to ml/models/evaluation_results.json and printed
to stdout for inclusion in the project report.
"""

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for server environments
import matplotlib.pyplot as plt
import seaborn as sns


def load_config(path: str = "ml/configs/training.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def compute_detection_delay(true_labels: np.ndarray,
                            pred_labels: np.ndarray,
                            timestamps: pd.Series,
                            interval_sec: int = 10) -> float:
    """
    For each contiguous anomaly window in the ground truth, find how
    many samples pass before the model first detects it.
    Returns the average delay in seconds.
    """
    delays = []
    in_anomaly = False
    window_start = None

    for i in range(len(true_labels)):
        if true_labels[i] == 1 and not in_anomaly:
            in_anomaly = True
            window_start = i
        elif true_labels[i] == 0 and in_anomaly:
            in_anomaly = False
            # Find first detection within this window
            window_preds = pred_labels[window_start:i]
            detected_indices = np.where(window_preds == 1)[0]
            if len(detected_indices) > 0:
                delay_samples = detected_indices[0]
                delays.append(delay_samples * interval_sec)
            else:
                # Missed entirely — count as the full window duration
                delays.append((i - window_start) * interval_sec)

    if len(delays) == 0:
        return 0.0
    return float(np.mean(delays))


def evaluate_model(model_artifact: dict, features: np.ndarray,
                   labels: np.ndarray) -> dict:
    """Score the test set and compute metrics."""
    model = model_artifact["model"]
    threshold = model_artifact["threshold"]

    t0 = time.time()
    scores = model.decision_function(features)
    inference_time = time.time() - t0

    preds = (scores < threshold).astype(int)

    tp = int(np.sum((preds == 1) & (labels == 1)))
    fp = int(np.sum((preds == 1) & (labels == 0)))
    tn = int(np.sum((preds == 0) & (labels == 0)))
    fn = int(np.sum((preds == 0) & (labels == 1)))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    accuracy = (tp + tn) / (tp + fp + tn + fn)

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "accuracy": round(accuracy, 4),
        "confusion_matrix": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn
        },
        "threshold_used": round(threshold, 4),
        "total_test_samples": len(labels),
        "anomaly_samples": int(labels.sum()),
        "inference_time_sec": round(inference_time, 4),
        "inference_latency_per_sample_ms": round(
            (inference_time / len(labels)) * 1000, 4
        ),
        "anomaly_scores_stats": {
            "mean": round(float(scores.mean()), 4),
            "std": round(float(scores.std()), 4),
            "min": round(float(scores.min()), 4),
            "max": round(float(scores.max()), 4)
        },
        "predictions": preds,
        "scores": scores
    }


def evaluate_baseline(baseline: dict, features: np.ndarray,
                      labels: np.ndarray) -> dict:
    """Evaluate the z-score threshold baseline for comparison."""
    train_mean = np.array(baseline["train_mean"])
    train_std = np.array(baseline["train_std"])
    train_std[train_std < 1e-8] = 1.0
    threshold = baseline["threshold"]

    # Use only the first len(train_mean) features (raw scaled features)
    subset = features[:, :len(train_mean)]
    z_scores = np.abs((subset - train_mean) / train_std)
    max_z = z_scores.max(axis=1)
    preds = (max_z > threshold).astype(int)

    tp = int(np.sum((preds == 1) & (labels == 1)))
    fp = int(np.sum((preds == 1) & (labels == 0)))
    tn = int(np.sum((preds == 0) & (labels == 0)))
    fn = int(np.sum((preds == 0) & (labels == 1)))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0)

    return {
        "method": "z_score_baseline",
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "confusion_matrix": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn
        }
    }


def plot_evaluation(results: dict, scores: np.ndarray, labels: np.ndarray,
                    output_dir: Path):
    """Generate evaluation plots for the report."""
    sns.set_style("darkgrid")

    # 1. Anomaly score distribution
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    normal_scores = scores[labels == 0]
    anomaly_scores = scores[labels == 1]

    axes[0].hist(normal_scores, bins=80, alpha=0.7, label="Normal",
                 color="#2196F3", density=True)
    axes[0].hist(anomaly_scores, bins=80, alpha=0.7, label="Anomaly",
                 color="#F44336", density=True)
    axes[0].axvline(x=results["threshold_used"], color="#FF9800",
                    linestyle="--", linewidth=2, label="Threshold")
    axes[0].set_xlabel("Anomaly Score (decision_function)")
    axes[0].set_ylabel("Density")
    axes[0].set_title("Score Distribution: Normal vs Anomalous")
    axes[0].legend()

    # 2. Confusion matrix heatmap
    cm = results["confusion_matrix"]
    cm_array = np.array([
        [cm["true_negatives"], cm["false_positives"]],
        [cm["false_negatives"], cm["true_positives"]]
    ])
    sns.heatmap(cm_array, annot=True, fmt="d", cmap="Blues",
                xticklabels=["Predicted Normal", "Predicted Anomaly"],
                yticklabels=["Actual Normal", "Actual Anomaly"],
                ax=axes[1])
    axes[1].set_title("Confusion Matrix")

    plt.tight_layout()
    fig.savefig(output_dir / "evaluation_plots.png", dpi=150,
                bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved evaluation plots to {output_dir / 'evaluation_plots.png'}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate anomaly model")
    parser.add_argument("--config", default="ml/configs/training.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    out_cfg = cfg["output"]
    processed_dir = Path(cfg["data"]["processed_path"]).parent

    # Load test data
    print("  Loading test data ...")
    test_df = pd.read_csv(processed_dir / "test_windowed.csv",
                          parse_dates=["timestamp"])

    # Load trained model
    model_artifact = joblib.load(out_cfg["forest_path"])
    feature_cols = model_artifact["feature_columns"]

    test_features = test_df[feature_cols].values
    test_labels = test_df["is_anomaly"].values

    # ----- Evaluate Isolation Forest -----
    print("\n  Evaluating Isolation Forest on test set ...")
    results = evaluate_model(model_artifact, test_features, test_labels)

    # Compute detection delay
    delay = compute_detection_delay(
        test_labels, results["predictions"], test_df["timestamp"]
    )
    results["detection_delay_seconds"] = round(delay, 2)

    print(f"\n  === Isolation Forest Results ===")
    print(f"    Precision:  {results['precision']}")
    print(f"    Recall:     {results['recall']}")
    print(f"    F1 Score:   {results['f1_score']}")
    print(f"    FPR:        {results['false_positive_rate']}")
    print(f"    Accuracy:   {results['accuracy']}")
    print(f"    Detection Delay: {results['detection_delay_seconds']}s")
    print(f"    Inference Latency: "
          f"{results['inference_latency_per_sample_ms']}ms/sample")
    cm = results["confusion_matrix"]
    print(f"    TP={cm['true_positives']}, FP={cm['false_positives']}, "
          f"TN={cm['true_negatives']}, FN={cm['false_negatives']}")

    # ----- Evaluate baseline -----
    baseline_path = Path(out_cfg["model_dir"]) / "baseline_threshold.json"
    baseline_results = None
    if baseline_path.exists():
        print("\n  Evaluating z-score baseline ...")
        with open(baseline_path, "r") as f:
            baseline = json.load(f)
        baseline_results = evaluate_baseline(baseline, test_features,
                                             test_labels)
        print(f"    Baseline F1: {baseline_results['f1_score']}")
        print(f"    IF beats baseline by: "
              f"{results['f1_score'] - baseline_results['f1_score']:.4f} F1")

    # ----- Generate plots -----
    model_dir = Path(out_cfg["model_dir"])
    plot_evaluation(results, results.pop("scores"),
                    test_labels, model_dir)

    # Remove non-serializable fields before saving
    results.pop("predictions", None)

    # ----- Save report -----
    evaluation_report = {
        "isolation_forest": results,
        "baseline": baseline_results,
        "model_version": model_artifact.get("model_version", "unknown"),
        "test_samples": len(test_labels),
        "test_anomaly_ratio": round(
            float(test_labels.sum()) / len(test_labels), 4
        )
    }

    eval_path = out_cfg["evaluation_path"]
    with open(eval_path, "w") as f:
        json.dump(evaluation_report, f, indent=2)
    print(f"\n  Saved evaluation report to {eval_path}")
    print("  Evaluation complete.")


if __name__ == "__main__":
    main()
