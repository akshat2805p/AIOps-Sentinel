"""
collect.py
----------
System metrics collector using psutil.
Gathers CPU, memory, disk I/O, network, and application-level metrics
at a configurable interval and sends them to the backend API.

Works on both Linux and Windows thanks to psutil's cross-platform API.
"""

import os
import platform
import socket
import time
from datetime import datetime, timezone

import psutil


def get_host_id() -> str:
    """Generate a stable host identifier."""
    hostname = socket.gethostname()
    return f"{hostname}-{platform.system().lower()}"


def collect_metrics() -> dict:
    """
    Gather a snapshot of current system metrics.
    Returns a dictionary matching the backend's expected schema.
    """
    # CPU — average over a 1-second interval for accuracy
    cpu_pct = psutil.cpu_percent(interval=1)

    # Memory
    mem = psutil.virtual_memory()
    mem_pct = mem.percent

    # Disk I/O — compute rate from counters
    disk_before = psutil.disk_io_counters()
    time.sleep(0.5)
    disk_after = psutil.disk_io_counters()

    if disk_before and disk_after:
        read_rate = (disk_after.read_bytes - disk_before.read_bytes) / 0.5
        write_rate = (disk_after.write_bytes - disk_before.write_bytes) / 0.5
        disk_io = read_rate + write_rate
    else:
        disk_io = 0.0

    # Network — compute rate similarly
    net_before = psutil.net_io_counters()
    time.sleep(0.5)
    net_after = psutil.net_io_counters()

    bytes_sent_rate = (net_after.bytes_sent - net_before.bytes_sent) / 0.5
    bytes_recv_rate = (net_after.bytes_recv - net_before.bytes_recv) / 0.5
    network_bytes = bytes_sent_rate + bytes_recv_rate

    # For request latency and error rate, we use synthetic defaults
    # since these would normally come from application-level instrumentation.
    # In production, you would integrate with your app's metrics endpoint.
    request_latency_ms = 0.0
    error_rate = 0.0

    timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "host_id": get_host_id(),
        "timestamp": timestamp,
        "metrics": {
            "cpu_percent": round(cpu_pct, 2),
            "memory_percent": round(mem_pct, 2),
            "disk_io_bytes_sec": round(disk_io, 2),
            "network_bytes_sec": round(network_bytes, 2),
            "request_latency_ms": round(request_latency_ms, 2),
            "error_rate": round(error_rate, 4)
        }
    }


def collect_extended_metrics() -> dict:
    """
    Extended metrics collection including per-CPU, per-disk, and
    top-process information.  Used for detailed dashboard views.
    """
    base = collect_metrics()

    # Per-CPU utilization
    per_cpu = psutil.cpu_percent(percpu=True)
    base["extended"] = {
        "per_cpu_percent": per_cpu,
        "cpu_count": psutil.cpu_count(),
        "load_avg": getattr(os, "getloadavg", lambda: (0, 0, 0))(),
        "swap_percent": psutil.swap_memory().percent,
        "disk_usage_percent": psutil.disk_usage("/").percent
            if platform.system() != "Windows"
            else psutil.disk_usage("C:\\").percent,
        "boot_time": datetime.fromtimestamp(
            psutil.boot_time(), tz=timezone.utc
        ).isoformat()
    }

    # Top 5 processes by CPU
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent",
                                      "memory_percent"]):
        try:
            info = proc.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda p: p.get("cpu_percent", 0) or 0, reverse=True)
    base["extended"]["top_processes"] = procs[:5]

    return base


if __name__ == "__main__":
    # Quick test — collect and print one snapshot
    import json
    snapshot = collect_metrics()
    print(json.dumps(snapshot, indent=2))
