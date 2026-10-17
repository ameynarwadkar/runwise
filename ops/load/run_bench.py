"""
Headless Load Test Driver and Capacity Benchmarking Script.

Executes Locust headless against http://127.0.0.1:8000, parses generated stats CSV,
and prints an empirical capacity & latency analysis.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "results" / "load_test"


def parse_locust_stats(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records


def format_benchmark_table(records: list[dict[str, str]]) -> str:
    lines = [
        "| Endpoint / User Flow | Requests | Failures | Median (ms) | p95 (ms) | p99 (ms) | Req/s |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for r in records:
        name = r.get("Name", "unknown")
        reqs = int(r.get("Request Count", 0))
        fails = int(r.get("Failure Count", 0))
        p50 = float(r.get("50%", 0.0))
        p95 = float(r.get("95%", 0.0))
        p99 = float(r.get("99%", 0.0))
        rps = float(r.get("Requests/s", 0.0))

        if name == "Aggregated":
            lines.append(f"| **{name}** | **{reqs:,}** | **{fails:,}** | **{p50:.1f}** | **{p95:.1f}** | **{p99:.1f}** | **{rps:.2f}** |")
        else:
            lines.append(f"| `{name}` | {reqs:,} | {fails:,} | {p50:.1f} | {p95:.1f} | {p99:.1f} | {rps:.2f} |")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run headless Locust benchmark")
    parser.add_argument("--users", "-u", type=int, default=5, help="Peak simulated concurrent users")
    parser.add_argument("--spawn-rate", "-r", type=int, default=1, help="Users spawned per second")
    parser.add_argument("--run-time", "-t", type=str, default="15s", help="Duration of load test (e.g. 15s, 30s, 1m)")
    parser.add_argument("--host", type=str, default="http://127.0.0.1:8000", help="Target service host")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_prefix = OUTPUT_DIR / "bench"

    cmd = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        str(PROJECT_ROOT / "ops" / "load" / "locustfile.py"),
        "--headless",
        "-u",
        str(args.users),
        "-r",
        str(args.spawn_rate),
        "-t",
        args.run_time,
        "--host",
        args.host,
        f"--csv={csv_prefix}",
    ]

    print("\n" + "=" * 75)
    print("  ⚡ EXECUTING RUNWISE CONCURRENCY BENCHMARK")
    print(f"  • Target Host:       {args.host}")
    print(f"  • Concurrent Users:  {args.users}")
    print(f"  • Spawn Rate:        {args.spawn_rate} users/sec")
    print(f"  • Test Duration:     {args.run_time}")
    print("=" * 75 + "\n")

    subprocess.run(cmd, check=True)

    stats_file = OUTPUT_DIR / "bench_stats.csv"
    records = parse_locust_stats(stats_file)

    print("\n" + "=" * 75)
    print("  📊 BENCHMARK CAPACITY & LATENCY RESULTS")
    print("=" * 75 + "\n")
    if records:
        print(format_benchmark_table(records))
    else:
        print("No CSV stats generated. Ensure service is active on host.")
    print("\n")


if __name__ == "__main__":
    main()
