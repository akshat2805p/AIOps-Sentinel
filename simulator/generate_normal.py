"""
generate_normal.py
------------------
Produces synthetic "normal operation" telemetry for one or more hosts.
Each row is a single metric observation at a fixed sampling interval,
with Gaussian noise shaped by the profile defined in scenarios.yaml.

Diurnal load patterns are layered on top so the data is not just pure
random noise — a reviewer can eyeball the CSVs and see believable
daily traffic cycles.

Output: ml/data/raw/normal_telemetry.csv
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def load_config(path: str) -> dict:
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def diurnal_factor(hour: float) -> float:
    """
    Attempt to mimic a realistic 24-hour traffic curve.
    Peak around 10–14h, trough around 3–5h.
    Returns a multiplier in roughly [0.4, 1.3].
    """
    # shifted cosine so the minimum is near 4 AM, peak near 1 PM
    return 1.0 + 0.3 * np.cos(2 * np.pi * (hour - 13) / 24)


def generate_metric(rng, profile: dict, n_points: int,
                    hours: np.ndarray) -> np.ndarray:
    """Sample n_points from a Gaussian, modulated by diurnal cycle."""
    base_mean = profile["mean"]
    base_std = profile["std"]
    lo, hi = profile["min"], profile["max"]

    factors = np.array([diurnal_factor(h) for h in hours])
    values = rng.normal(loc=base_mean * factors, scale=base_std, size=n_points)
    return np.clip(values, lo, hi)


def main():
    parser = argparse.ArgumentParser(
        description="Generate normal-operation server telemetry"
    )
    parser.add_argument(
        "--config", default="simulator/scenarios.yaml",
        help="Path to scenarios YAML"
    )
    parser.add_argument(
        "--output", default="ml/data/raw/normal_telemetry.csv",
        help="Output CSV path"
    )
    parser.add_argument("--days", type=int, default=None,
                        help="Override number of days to generate")
    parser.add_argument("--seed", type=int, default=None,
                        help="Override random seed")
    args = parser.parse_args()

    cfg = load_config(args.config)
    gen_cfg = cfg["generation"]

    days = args.days if args.days else gen_cfg.get("normal_days", 7)
    seed = args.seed if args.seed else gen_cfg.get("seed", 42)
    interval = gen_cfg.get("interval_seconds", 10)
    hosts = gen_cfg.get("hosts", ["server-01"])

    rng = np.random.default_rng(seed)

    # Build the timeline
    start = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    total_seconds = days * 86400
    n_points = total_seconds // interval

    timestamps = [start + timedelta(seconds=i * interval)
                  for i in range(n_points)]
    hours = np.array([t.hour + t.minute / 60.0 for t in timestamps])

    metric_cols = [
        "cpu_percent", "memory_percent", "disk_io_bytes_sec",
        "network_bytes_sec", "request_latency_ms", "error_rate"
    ]

    all_rows = []

    for host_id in hosts:
        # Pick a profile — rotate between web_server and database_server
        if "db" in host_id or host_id == "server-03":
            profile_name = "database_server"
        else:
            profile_name = "web_server"

        profile = cfg["normal_profiles"][profile_name]
        host_data = {"timestamp": timestamps, "host_id": [host_id] * n_points}

        for col in metric_cols:
            host_data[col] = generate_metric(rng, profile[col], n_points, hours)

        all_rows.append(pd.DataFrame(host_data))
        print(f"  Generated {n_points} normal samples for {host_id} "
              f"({profile_name})")

    df = pd.concat(all_rows, ignore_index=True)
    df.sort_values(["timestamp", "host_id"], inplace=True)

    # Make sure the output directory exists
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"\nWrote {len(df)} rows to {args.output}")


if __name__ == "__main__":
    main()
