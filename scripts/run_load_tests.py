import subprocess
import os
import sys
import time
import json
import psutil
import csv
import asyncio
import websockets

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_EXE = os.path.join(BASE_DIR, "backend", "venv", "Scripts", "python.exe")
LOCUST_EXE = os.path.join(BASE_DIR, "backend", "venv", "Scripts", "locust.exe")
RESULTS_DIR = os.path.join(BASE_DIR, "performance_results")
os.makedirs(RESULTS_DIR, exist_ok=True)

USER_TIERS = [10, 25, 50, 100]
RUN_TIME_SECONDS = 15

async def test_websocket_concurrency(target_concurrency=100):
    """Measures WebSocket concurrent connections and round-trip ping latency."""
    uri = "ws://127.0.0.1:8000/ws/general"

    print(f"\n--- Testing WebSocket Concurrency (Target: {target_concurrency} active sockets) ---", flush=True)

    async def worker(socket_id: int):
        t0 = time.time()
        async with websockets.connect(uri, ping_interval=None) as ws:
            t1 = time.time()
            await ws.send(f"PING_{socket_id}")
            msg = await ws.recv()
            t2 = time.time()
            return {
                "connect_ms": (t1 - t0) * 1000,
                "ping_rtt_ms": (t2 - t1) * 1000,
                "status": "success"
            }

    try:
        tasks = [worker(i) for i in range(target_concurrency)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = [r for r in results if isinstance(r, dict) and r.get("status") == "success"]
        failed_count = target_concurrency - len(valid_results)

        conn_times = [r["connect_ms"] for r in valid_results]
        ping_times = [r["ping_rtt_ms"] for r in valid_results]

        avg_conn = sum(conn_times) / len(conn_times) if conn_times else 0
        avg_ping = sum(ping_times) / len(ping_times) if ping_times else 0
        sorted_ping = sorted(ping_times)
        p95_ping = sorted_ping[int(len(sorted_ping) * 0.95)] if sorted_ping else 0
        p99_ping = sorted_ping[int(len(sorted_ping) * 0.99)] if sorted_ping else 0

        res = {
            "target_concurrency": target_concurrency,
            "connected_count": len(valid_results),
            "failed_count": failed_count,
            "avg_connection_time_ms": round(avg_conn, 2),
            "avg_ping_rtt_ms": round(avg_ping, 2),
            "p95_ping_rtt_ms": round(p95_ping, 2),
            "p99_ping_rtt_ms": round(p99_ping, 2),
            "success": failed_count == 0
        }
        print(f"WebSocket Benchmark Results: {res}", flush=True)
        return res
    except Exception as e:
        print(f"WebSocket Concurrency Exception: {e}", flush=True)
        return {"error": str(e), "target_concurrency": target_concurrency}

def run_tier(users: int, spawn_rate: int):
    csv_prefix = os.path.join(RESULTS_DIR, f"tier_{users}")
    locustfile = os.path.join(BASE_DIR, "scripts", "locustfile.py")
    host = "http://127.0.0.1:8000"
    log_file = os.path.join(RESULTS_DIR, f"tier_{users}.log")

    print(f"\n=======================================================", flush=True)
    print(f"  EXECUTING LOAD TEST: {users} CONCURRENT USERS ({RUN_TIME_SECONDS}s)", flush=True)
    print(f"=======================================================", flush=True)

    cmd = [
        LOCUST_EXE,
        "-f", locustfile,
        "--headless",
        "-u", str(users),
        "-r", str(spawn_rate),
        "-t", f"{RUN_TIME_SECONDS}s",
        "--host", host,
        "--csv", csv_prefix,
        "--only-summary"
    ]

    cpu_samples = []
    mem_samples = []

    with open(log_file, "w", encoding="utf-8") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=lf, text=True)

        start_t = time.time()
        # Sample CPU/RAM while running
        while proc.poll() is None:
            cpu_samples.append(psutil.cpu_percent(interval=0.5))
            mem_samples.append(psutil.virtual_memory().percent)
            if time.time() - start_t > RUN_TIME_SECONDS + 25:
                print(f"Timeout reached for tier {users}, terminating process...", flush=True)
                proc.terminate()
                break

    # Parse generated CSV stats
    stats_file = f"{csv_prefix}_stats.csv"
    tier_summary = {
        "users": users,
        "run_time_s": RUN_TIME_SECONDS,
        "total_requests": 0,
        "failed_requests": 0,
        "rps": 0.0,
        "avg_response_time_ms": 0.0,
        "median_response_time_ms": 0.0,
        "p95_response_time_ms": 0.0,
        "p99_response_time_ms": 0.0,
        "error_rate_percent": 0.0,
        "avg_cpu_percent": round(sum(cpu_samples) / max(1, len(cpu_samples)), 1),
        "avg_mem_percent": round(sum(mem_samples) / max(1, len(mem_samples)), 1),
        "endpoints": []
    }

    if os.path.exists(stats_file):
        with open(stats_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Name", "")
                if name == "Aggregated":
                    tier_summary["total_requests"] = int(row.get("Request Count", 0))
                    tier_summary["failed_requests"] = int(row.get("Failure Count", 0))
                    tier_summary["median_response_time_ms"] = float(row.get("Median Response Time", 0))
                    tier_summary["avg_response_time_ms"] = round(float(row.get("Average Response Time", 0)), 2)
                    tier_summary["rps"] = round(float(row.get("Requests/s", 0)), 2)
                    try:
                        tier_summary["p95_response_time_ms"] = float(row.get("95%", 0))
                        tier_summary["p99_response_time_ms"] = float(row.get("99%", 0))
                    except Exception:
                        pass
                    tier_summary["error_rate_percent"] = round(
                        (tier_summary["failed_requests"] / max(1, tier_summary["total_requests"])) * 100.0, 2
                    )
                elif name and name != "Total":
                    tier_summary["endpoints"].append({
                        "endpoint": name,
                        "requests": int(row.get("Request Count", 0)),
                        "failures": int(row.get("Failure Count", 0)),
                        "median_ms": float(row.get("Median Response Time", 0)),
                        "avg_ms": round(float(row.get("Average Response Time", 0)), 2),
                        "rps": round(float(row.get("Requests/s", 0)), 2)
                    })

    print(f"Summary for {users} Users:", flush=True)
    print(f"  Requests: {tier_summary['total_requests']}, RPS: {tier_summary['rps']}, Error Rate: {tier_summary['error_rate_percent']}%", flush=True)
    print(f"  Avg Latency: {tier_summary['avg_response_time_ms']}ms, Median: {tier_summary['median_response_time_ms']}ms, P95: {tier_summary['p95_response_time_ms']}ms, P99: {tier_summary['p99_response_time_ms']}ms", flush=True)
    print(f"  CPU: {tier_summary['avg_cpu_percent']}%, Memory: {tier_summary['avg_mem_percent']}%", flush=True)

    return tier_summary

def main():
    all_results = []
    spawn_rates = {10: 5, 25: 10, 50: 20, 100: 30}

    for u in USER_TIERS:
        res = run_tier(u, spawn_rates[u])
        all_results.append(res)
        time.sleep(3)  # Cooldown between test tiers

    # Cooldown before WebSocket load test
    time.sleep(3)
    ws_results = asyncio.run(test_websocket_concurrency(target_concurrency=100))

    final_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "test_duration_per_tier_seconds": RUN_TIME_SECONDS,
        "tiers": all_results,
        "websocket_concurrency": ws_results
    }

    report_path = os.path.join(RESULTS_DIR, "performance_summary.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2)

    print(f"\nAll load test runs successfully saved to {report_path}", flush=True)

if __name__ == "__main__":
    main()
