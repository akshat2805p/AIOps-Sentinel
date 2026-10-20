"""
client.py
---------
Collector daemon that periodically gathers metrics and pushes them
to the backend API.  Runs as a background service.

Usage:
    python -m collector.sentinel_collector.client
    python -m collector.sentinel_collector.client --interval 10 --url http://localhost:8080/api/v1/metrics
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

import requests

from collector.sentinel_collector.collect import collect_metrics, get_host_id


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("sentinel-collector")

# Graceful shutdown flag
_running = True


def handle_shutdown(signum, frame):
    global _running
    logger.info("Shutdown signal received, stopping collector ...")
    _running = False


def register_host(api_url: str, host_id: str) -> bool:
    """Register this host with the backend if not already known."""
    import socket
    import platform

    base_url = api_url.rsplit("/metrics", 1)[0]
    register_url = f"{base_url}/hosts"

    payload = {
        "host_id": host_id,
        "hostname": socket.gethostname(),
        "ip_address": socket.gethostbyname(socket.gethostname()),
        "os_info": f"{platform.system()} {platform.release()}"
    }

    try:
        resp = requests.post(register_url, json=payload, timeout=5)
        if resp.status_code in (200, 201, 409):
            logger.info(f"Host registered: {host_id}")
            return True
        else:
            logger.warning(f"Host registration returned {resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.warning("Backend not reachable — will retry on next cycle")
        return False


def send_metrics(api_url: str, payload: dict) -> bool:
    """POST metrics to the backend API."""
    try:
        resp = requests.post(api_url, json=payload, timeout=10)
        if resp.status_code in (200, 201):
            return True
        else:
            logger.warning(f"Backend returned {resp.status_code}: "
                           f"{resp.text[:200]}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("Cannot reach backend at %s", api_url)
        return False
    except requests.exceptions.Timeout:
        logger.error("Request to backend timed out")
        return False


def run_collector(api_url: str, interval: int):
    """Main collection loop."""
    host_id = get_host_id()
    logger.info(f"Starting collector for host: {host_id}")
    logger.info(f"Sending metrics to: {api_url}")
    logger.info(f"Collection interval: {interval}s")

    register_host(api_url, host_id)

    consecutive_failures = 0
    max_backoff = 60  # seconds

    while _running:
        try:
            snapshot = collect_metrics()
            success = send_metrics(api_url, snapshot)

            if success:
                consecutive_failures = 0
                logger.debug("Metrics sent successfully")
            else:
                consecutive_failures += 1

        except Exception as exc:
            consecutive_failures += 1
            logger.error(f"Collection error: {exc}")

        # Exponential backoff on repeated failures
        if consecutive_failures > 3:
            backoff = min(interval * (2 ** (consecutive_failures - 3)),
                          max_backoff)
            logger.warning(f"Backing off for {backoff:.0f}s after "
                           f"{consecutive_failures} failures")
            time.sleep(backoff)
        else:
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description="AIOps Sentinel Metrics Collector"
    )
    parser.add_argument(
        "--url",
        default=os.getenv("COLLECTOR_TARGET_URL",
                          "http://localhost:8080/api/v1/metrics"),
        help="Backend metrics endpoint URL"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("COLLECTOR_INTERVAL_SEC", "5")),
        help="Collection interval in seconds"
    )
    args = parser.parse_args()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    run_collector(args.url, args.interval)
    logger.info("Collector stopped.")


if __name__ == "__main__":
    main()
