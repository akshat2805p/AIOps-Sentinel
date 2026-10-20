"""
inject_anomalies.py
-------------------
Takes the clean normal telemetry and injects anomaly windows based on
the scenario definitions in scenarios.yaml.

Each injection:
  1.  Picks a random start time within the dataset
  2.  Picks a random duration from the scenario range
  3.  Overwrites / multiplies metric values in that window
  4.  Labels every affected row with is_anomaly=1 and the scenario name

This gives us a ground-truth-labeled dataset suitable for training
and evaluating the anomaly detector.

Output: ml/data/raw/labeled_telemetry.csv
"""

import argparse
import os
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def load_config(path: str) -> dict:
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def inject_scenario(df_host: pd.DataFrame, scenario: dict,
                    scenario_name: str, rng,
                    interval_sec: int) -> pd.DataFrame:
    """
    Pick a random window in df_host and modify metrics according to
    the scenario spec.  Returns a modified copy.
    """
    dur_range = scenario["duration_minutes"]
    duration_min = rng.integers(dur_range[0], dur_range[1] + 1)
    n_rows_in_window = (duration_min * 60) // interval_sec

    # Make sure window fits inside the dataframe
    max_start = len(df_host) - n_rows_in_window - 1
    if max_start < 1:
        return df_host  # dataset too small for this scenario
    start_idx = rng.integers(0, max_start)
    end_idx = start_idx + n_rows_in_window

    affected = scenario.get("affected_metrics", {})
    is_ramp = scenario.get("ramp") == "linear"

    for metric_name, spec in affected.items():
        if metric_name not in df_host.columns:
            continue

        original = df_host[metric_name].values.copy()

        if is_ramp and "start" in spec and "end" in spec:
            # Linear ramp from start value to end value
            ramp_vals = np.linspace(spec["start"], spec["end"],
                                    n_rows_in_window)
            noise = rng.normal(0, 1.0, n_rows_in_window)
            original[start_idx:end_idx] = ramp_vals + noise
        elif "override_mean" in spec:
            override_std = spec.get("override_std", 2.0)
            injected = rng.normal(spec["override_mean"], override_std,
                                  n_rows_in_window)
            original[start_idx:end_idx] = injected
        elif "multiplier" in spec:
            original[start_idx:end_idx] *= spec["multiplier"]

        # Clamp non-negative (all our metrics should be >= 0)
        original = np.clip(original, 0, None)
        # Special clamp for percentage metrics
        if "percent" in metric_name:
            original = np.clip(original, 0, 100)
        if metric_name == "error_rate":
            original = np.clip(original, 0, 1)

        df_host[metric_name] = original

    # Label the anomaly window
    labels = df_host["is_anomaly"].values.copy()
    labels[start_idx:end_idx] = 1
    df_host["is_anomaly"] = labels

    categories = df_host["anomaly_type"].values.copy()
    for i in range(start_idx, end_idx):
        existing = categories[i]
        if existing == "normal":
            categories[i] = scenario_name
        else:
            categories[i] = existing + "+" + scenario_name
    df_host["anomaly_type"] = categories

    window_start = df_host.iloc[start_idx]["timestamp"]
    window_end = df_host.iloc[end_idx - 1]["timestamp"]
    print(f"    Injected '{scenario_name}' for host "
          f"({n_rows_in_window} rows, {duration_min} min) "
          f"from {window_start} to {window_end}")

    return df_host


def main():
    parser = argparse.ArgumentParser(
        description="Inject anomaly scenarios into normal telemetry"
    )
    parser.add_argument(
        "--config", default="simulator/scenarios.yaml",
        help="Scenarios YAML"
    )
    parser.add_argument(
        "--input", default="ml/data/raw/normal_telemetry.csv",
        help="Normal telemetry CSV"
    )
    parser.add_argument(
        "--output", default="ml/data/raw/labeled_telemetry.csv",
        help="Output CSV with anomaly labels"
    )
    parser.add_argument("--injections-per-host", type=int, default=8,
                        help="How many anomaly windows per host")
    parser.add_argument("--seed", type=int, default=123)
    args = parser.parse_args()

    cfg = load_config(args.config)
    rng = np.random.default_rng(args.seed)

    df = pd.read_csv(args.input, parse_dates=["timestamp"])
    df["is_anomaly"] = 0
    df["anomaly_type"] = "normal"

    interval = cfg["generation"].get("interval_seconds", 10)
    scenario_names = list(cfg["anomaly_scenarios"].keys())

    hosts = df["host_id"].unique()
    frames = []

    for host_id in hosts:
        print(f"\n  Processing host: {host_id}")
        df_host = df[df["host_id"] == host_id].copy().reset_index(drop=True)

        for i in range(args.injections_per_host):
            # Round-robin through scenarios, then random
            sname = scenario_names[i % len(scenario_names)]
            if i >= len(scenario_names):
                sname = rng.choice(scenario_names)
            scenario = cfg["anomaly_scenarios"][sname]
            df_host = inject_scenario(df_host, scenario, sname, rng, interval)

        frames.append(df_host)

    result = pd.concat(frames, ignore_index=True)
    result.sort_values(["timestamp", "host_id"], inplace=True)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)

    n_anomaly = result["is_anomaly"].sum()
    n_total = len(result)
    pct = 100.0 * n_anomaly / n_total
    print(f"\nDone — {n_total} total rows, {n_anomaly} anomalous ({pct:.1f}%)")
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
