"""
make_windows.py
---------------
Converts the flat per-observation features into rolling-window
feature vectors.  For each observation at time t, we compute:

  - Rolling mean and standard deviation over the past W observations
  - Rate-of-change (first differences) at specified lags

This captures temporal patterns that a point-in-time snapshot misses.
A sudden jump in CPU from 30% to 90% is only visible through the
difference features, not from the 90% value alone.

Input:  ml/data/processed/{train,val,test}.csv
Output: ml/data/processed/{train,val,test}_windowed.csv
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def load_config(path: str = "ml/configs/training.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def build_rolling_features(df: pd.DataFrame, metric_cols: list,
                           windows: list, stats: list) -> pd.DataFrame:
    """
    For each metric column, compute rolling statistics within each host
    group.  This avoids crossing host boundaries.
    """
    new_cols = {}

    for host_id, grp in df.groupby("host_id"):
        for col in metric_cols:
            scaled_col = f"{col}_scaled"
            if scaled_col not in grp.columns:
                continue

            series = grp[scaled_col]

            for w in windows:
                roller = series.rolling(window=w, min_periods=1)
                for stat in stats:
                    feat_name = f"{col}_roll{w}_{stat}"
                    if feat_name not in new_cols:
                        new_cols[feat_name] = pd.Series(
                            dtype="float64", index=df.index
                        )
                    if stat == "mean":
                        new_cols[feat_name].loc[grp.index] = roller.mean()
                    elif stat == "std":
                        vals = roller.std()
                        # std of a single element is NaN; fill with 0
                        vals = vals.fillna(0.0)
                        new_cols[feat_name].loc[grp.index] = vals

    for name, series in new_cols.items():
        df[name] = series

    return df


def build_diff_features(df: pd.DataFrame, metric_cols: list,
                        lags: list) -> pd.DataFrame:
    """
    Compute rate-of-change features: x(t) - x(t - lag).
    Done per-host to avoid cross-host contamination.
    """
    new_cols = {}

    for host_id, grp in df.groupby("host_id"):
        for col in metric_cols:
            scaled_col = f"{col}_scaled"
            if scaled_col not in grp.columns:
                continue

            for lag in lags:
                feat_name = f"{col}_diff{lag}"
                if feat_name not in new_cols:
                    new_cols[feat_name] = pd.Series(
                        dtype="float64", index=df.index
                    )
                diff_vals = grp[scaled_col].diff(periods=lag).fillna(0.0)
                new_cols[feat_name].loc[grp.index] = diff_vals

    for name, series in new_cols.items():
        df[name] = series

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Build rolling-window features for ML training"
    )
    parser.add_argument("--config", default="ml/configs/training.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    feat_cfg = cfg["features"]

    metric_cols = feat_cfg["raw_metrics"]
    windows = feat_cfg.get("rolling_windows", [6, 30])
    stats = feat_cfg.get("rolling_stats", ["mean", "std"])
    diff_lags = feat_cfg.get("diff_lags", [1, 6])

    processed_dir = Path(cfg["data"]["processed_path"]).parent

    for split_name in ["train", "val", "test"]:
        input_path = processed_dir / f"{split_name}.csv"
        output_path = processed_dir / f"{split_name}_windowed.csv"

        if not input_path.exists():
            print(f"  Skipping {split_name} — {input_path} not found")
            continue

        print(f"  Processing {split_name} ...")
        df = pd.read_csv(input_path, parse_dates=["timestamp"])

        df = build_rolling_features(df, metric_cols, windows, stats)
        df = build_diff_features(df, metric_cols, diff_lags)

        # Drop rows where rolling stats couldn't be computed (first few rows)
        # Actually we used min_periods=1 so we keep all rows, but NaN check:
        feature_cols = [c for c in df.columns if ("_roll" in c or "_diff" in c
                                                  or "_scaled" in c)]
        df[feature_cols] = df[feature_cols].fillna(0.0)

        df.to_csv(output_path, index=False)
        print(f"    {len(df)} rows, {len(feature_cols)} engineered features")
        print(f"    Saved to {output_path}")

    print("\n  Feature engineering complete.")


if __name__ == "__main__":
    main()
