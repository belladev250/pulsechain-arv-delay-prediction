"""Performance and stress check against a running backend.

Usage: python3 scripts/perf_test.py [base_url]
Measures single-request latency for the main endpoints, then fires concurrent requests and reports errors.
"""
import json
import platform
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
SHIPMENT = {"vendor": "SCMS from RDC", "country": "Burundi", "shipment_mode": "Truck", "inco_term": "N/A - From RDC",
            "fulfill_via": "From RDC", "product_group": "ARV", "quantity": 5000, "value": 50000}


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
            status = resp.status
    except urllib.error.HTTPError as err:
        status = err.code
    return status, (time.perf_counter() - start) * 1000


def summarise(times):
    ordered = sorted(times)
    return (f"mean {statistics.mean(times):7.1f} ms   median {statistics.median(times):7.1f} ms   "
            f"p95 {ordered[int(0.95 * (len(ordered) - 1))]:7.1f} ms   max {max(times):7.1f} ms")


def login():
    req = urllib.request.Request(BASE + "/api/auth/login", method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"email": "admin@pulsechain.local", "password": "Admin#2026"}).encode())
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["token"]


def main():
    print(f"Machine: {platform.platform()} | Python {platform.python_version()} | {platform.processor() or platform.machine()}")
    print(f"Target : {BASE}\n")
    token = login()
    scenarios = [("GET  /api/health", "GET", "/api/health", None),
                 ("POST /api/predict (SHAP explanation)", "POST", "/api/predict", SHIPMENT),
                 ("GET  /api/shipments (ranked)", "GET", "/api/shipments?limit=40", None),
                 ("GET  /api/dashboard", "GET", "/api/dashboard", None),
                 ("GET  /api/analytics", "GET", "/api/analytics", None)]
    print("1. Single-user latency (30 requests each, first one is a warm-up)")
    for name, method, path, body in scenarios:
        call(method, path, body, token)
        runs = [call(method, path, body, token) for _ in range(30)]
        bad = sum(1 for status, _ in runs if status != 200)
        print(f"   {name:40s} {summarise([t for _, t in runs])}   errors {bad}")

    print("\n2. Stress test: 20 parallel users x 10 predictions each (200 requests)")
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda _: call("POST", "/api/predict", SHIPMENT, token), range(200)))
    elapsed = time.perf_counter() - start
    times = [t for _, t in results]
    errors = sum(1 for status, _ in results if status != 200)
    print(f"   {summarise(times)}")
    print(f"   throughput {200 / elapsed:.1f} requests/s   errors {errors} of 200")
    print("\nRequirement NFR1: a single prediction must return in under 2000 ms.")
    single = [call("POST", "/api/predict", SHIPMENT, token)[1] for _ in range(20)]
    print("   NFR1:", "PASS" if max(single) < 2000 else "FAIL", f"(slowest of 20 = {max(single):.0f} ms)")


if __name__ == "__main__":
    main()
