# client.py
import requests, time, numpy as np, argparse, os
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["app","proxy","network"], required=True)
parser.add_argument("--n", type=int, default=1000)
parser.add_argument("--hist", action="store_true", help="show histogram")
args = parser.parse_args()

host = os.environ.get("HOST", "http://127.0.0.1:8080")
url = f"{host}/work?mode={args.mode}"
latencies = []
errors = 0

for i in range(args.n):
    start = time.time()
    try:
        r = requests.get(url, timeout=10)
        elapsed_ms = (time.time() - start) * 1000
        latencies.append(elapsed_ms)
    except Exception as e:
        errors += 1

if latencies:
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    print(f"Mode: {args.mode}  Requests: {args.n}  Errors: {errors}")
    print(f"p50: {p50:.2f} ms   p95: {p95:.2f} ms   p99: {p99:.2f} ms")
else:
    print("No successful requests.")

if args.hist and latencies:
    plt.hist(latencies, bins=60)
    plt.title(f"Latency distribution ({args.mode})")
    plt.xlabel("Latency (ms)")
    plt.ylabel("Count")
    plt.show()
