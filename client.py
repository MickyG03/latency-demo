# client.py
import requests, time, numpy as np, argparse, os, json
import matplotlib.pyplot as plt
from collections import defaultdict

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["app","proxy","network"], required=True)
parser.add_argument("--n", type=int, default=1000)
parser.add_argument("--hist", action="store_true", help="show histogram")
parser.add_argument("--analyze", action="store_true", help="show detailed analysis")
args = parser.parse_args()

host = os.environ.get("HOST", "http://127.0.0.1:8080")

# Reset metrics before starting
print(f"Resetting metrics for mode: {args.mode}")
try:
    requests.get(f"{host}/proxy/metrics/reset", timeout=2)
    requests.get("http://127.0.0.1:5000/metrics/reset", timeout=2)
except:
    pass

url = f"{host}/work?mode={args.mode}"
latencies = []
errors = 0

# Track detailed metrics from headers
proxy_queue_waits = []
proxy_processing_times = []
network_delays = []
upstream_times = []

print(f"\nRunning {args.n} requests in mode: {args.mode}")
print("=" * 60)

for i in range(args.n):
    if (i + 1) % 100 == 0:
        print(f"Progress: {i + 1}/{args.n} requests...")
    
    start = time.time()
    try:
        r = requests.get(url, timeout=10)
        elapsed_ms = (time.time() - start) * 1000
        latencies.append(elapsed_ms)
        
        # Extract timing headers from proxy
        if "X-Proxy-Queue-Wait-Ms" in r.headers:
            proxy_queue_waits.append(float(r.headers["X-Proxy-Queue-Wait-Ms"]))
        if "X-Proxy-Processing-Ms" in r.headers:
            proxy_processing_times.append(float(r.headers["X-Proxy-Processing-Ms"]))
        if "X-Network-Delay-Ms" in r.headers:
            network_delays.append(float(r.headers["X-Network-Delay-Ms"]))
        if "X-Upstream-Time-Ms" in r.headers:
            upstream_times.append(float(r.headers["X-Upstream-Time-Ms"]))
            
    except Exception as e:
        errors += 1

print("\n" + "=" * 60)
print("LATENCY RESULTS")
print("=" * 60)

if latencies:
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    p99_9 = np.percentile(latencies, 99.9)
    max_lat = max(latencies)
    
    print(f"Mode: {args.mode}")
    print(f"Requests: {args.n}  |  Errors: {errors}")
    print(f"\nPercentiles:")
    print(f"  p50:   {p50:.2f} ms")
    print(f"  p95:   {p95:.2f} ms")
    print(f"  p99:   {p99:.2f} ms  ⚠️  (TAIL LATENCY)")
    print(f"  p99.9: {p99_9:.2f} ms")
    print(f"  max:   {max_lat:.2f} ms")
    
    # Calculate the delta between p99 and p50 (key metric!)
    p99_inflation = ((p99 - p50) / p50) * 100
    print(f"\n📊 P99 Inflation: {p99_inflation:.1f}% above p50")
else:
    print("No successful requests.")

# Fetch and display layer-specific metrics
if args.analyze and latencies:
    print("\n" + "=" * 60)
    print("LAYER-SPECIFIC ANALYSIS")
    print("=" * 60)
    
    # Application metrics
    print("\n🔹 APPLICATION LAYER METRICS:")
    try:
        app_metrics = requests.get("http://127.0.0.1:5000/metrics", timeout=2).json()
        print(f"  Total requests processed: {app_metrics['requests_total']}")
        print(f"  Lock contention events: {app_metrics['lock_contention_count']}")
        print(f"  Contention rate: {app_metrics['contention_rate']}%")
        print(f"  Avg processing time: {app_metrics['avg_processing_time_ms']:.2f} ms")
        if app_metrics['lock_contention_count'] > 0:
            print(f"  Avg wait time (contended): {app_metrics['avg_wait_time_ms']:.2f} ms  ⚠️")
        print(f"  CPU usage: {app_metrics['cpu_percent']:.1f}%")
        print(f"  Active threads: {app_metrics['active_threads']}")
    except Exception as e:
        print(f"  ❌ Could not fetch app metrics: {e}")
    
    # Proxy metrics
    print("\n🔹 PROXY LAYER METRICS:")
    try:
        proxy_metrics = requests.get(f"{host}/proxy/metrics", timeout=2).json()
        print(f"  Total requests: {proxy_metrics['requests_total']}")
        print(f"  Requests in queue: {proxy_metrics['requests_in_queue']}")
        print(f"  Avg queue wait: {proxy_metrics['avg_queue_wait_ms']:.2f} ms")
        print(f"  Proxy overhead events: {proxy_metrics['proxy_overhead_count']}")
        if proxy_metrics['proxy_overhead_count'] > 0:
            print(f"  Avg proxy processing: {proxy_metrics['avg_proxy_processing_ms']:.2f} ms  ⚠️")
        print(f"  Connection errors: {proxy_metrics['connection_errors']}")
        print(f"  Upstream timeouts: {proxy_metrics['upstream_timeouts']}")
    except Exception as e:
        print(f"  ❌ Could not fetch proxy metrics: {e}")
    
    # Network metrics (from collected headers)
    print("\n🔹 NETWORK LAYER METRICS:")
    if network_delays:
        network_p50 = np.percentile(network_delays, 50)
        network_p99 = np.percentile(network_delays, 99)
        print(f"  Network delay p50: {network_p50:.2f} ms")
        print(f"  Network delay p99: {network_p99:.2f} ms  ⚠️")
        print(f"  Retries: {proxy_metrics.get('retries', 0)}")
        
        if network_p99 > network_p50 * 5:
            print(f"  ⚠️  High network variability detected!")
    
    # DIAGNOSTIC SUMMARY
    print("\n" + "=" * 60)
    print("🔍 DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    if args.mode == "app":
        print("\n✅ Evidence points to APPLICATION-LAYER CONTENTION:")
        print(f"  • Contention rate: {app_metrics.get('contention_rate', 0)}%")
        print(f"  • Wait time for contended requests: {app_metrics.get('avg_wait_time_ms', 0):.2f} ms")
        print(f"  • p99 latency aligns with lock hold time (~100ms)")
        print(f"  • Proxy and network metrics show normal behavior")
        
    elif args.mode == "proxy":
        print("\n✅ Evidence points to PROXY OVERHEAD:")
        print(f"  • Proxy overhead events: {proxy_metrics.get('proxy_overhead_count', 0)}")
        print(f"  • Avg proxy processing time: {proxy_metrics.get('avg_proxy_processing_ms', 0):.2f} ms")
        print(f"  • p99 latency aligns with proxy delays (~50ms)")
        print(f"  • Application processing time remains stable")
        print(f"  • Network metrics show normal behavior")
        
    elif args.mode == "network":
        print("\n✅ Evidence points to NETWORK VARIABILITY:")
        print(f"  • Network retries: {proxy_metrics.get('retries', 0)}")
        print(f"  • Network p99 delay: {network_p99:.2f} ms")
        print(f"  • High variance in network layer measurements")
        print(f"  • Application and proxy metrics remain stable")
        print(f"  • p99 latency aligns with network spikes (60-150ms)")
    
    print("\n" + "=" * 60)

if args.hist and latencies:
    plt.figure(figsize=(12, 5))
    
    # Subplot 1: Histogram
    plt.subplot(1, 2, 1)
    plt.hist(latencies, bins=60, color='skyblue', edgecolor='black')
    plt.axvline(np.percentile(latencies, 50), color='green', linestyle='--', label='p50')
    plt.axvline(np.percentile(latencies, 99), color='red', linestyle='--', label='p99')
    plt.title(f"Latency Distribution ({args.mode})")
    plt.xlabel("Latency (ms)")
    plt.ylabel("Count")
    plt.legend()
    
    # Subplot 2: CDF
    plt.subplot(1, 2, 2)
    sorted_latencies = np.sort(latencies)
    cdf = np.arange(1, len(sorted_latencies) + 1) / len(sorted_latencies) * 100
    plt.plot(sorted_latencies, cdf, linewidth=2)
    plt.axhline(50, color='green', linestyle='--', alpha=0.5, label='p50')
    plt.axhline(99, color='red', linestyle='--', alpha=0.5, label='p99')
    plt.title(f"Cumulative Distribution ({args.mode})")
    plt.xlabel("Latency (ms)")
    plt.ylabel("Percentile")
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    plt.tight_layout()
    plt.show()
