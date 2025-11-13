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
latency_timestamps = []  # Track when each request completed
errors = 0

# Track detailed metrics from headers
proxy_queue_waits = []
proxy_processing_times = []
network_delays = []
upstream_times = []

# Track application metrics over time
app_metrics_timeline = {
    'timestamps': [],
    'cpu_usage': [],
    'active_threads': [],
    'lock_contention_count': [],
    'requests_waiting': [],
}

# Track proxy metrics over time
proxy_metrics_timeline = {
    'timestamps': [],
    'requests_in_queue': [],
    'proxy_overhead_count': [],
    'avg_queue_wait': [],
    'connection_errors': [],
    'retries': [],
}

print(f"\nRunning {args.n} requests in mode: {args.mode}")
print("=" * 60)

start_time = time.time()

for i in range(args.n):
    if (i + 1) % 100 == 0:
        print(f"Progress: {i + 1}/{args.n} requests...")
    
    # Poll metrics every 10 requests to track over time
    if i % 10 == 0:
        try:
            # Always poll app metrics
            app_resp = requests.get("http://127.0.0.1:5000/metrics", timeout=1).json()
            app_metrics_timeline['timestamps'].append(time.time() - start_time)
            app_metrics_timeline['cpu_usage'].append(app_resp.get('cpu_percent', 0))
            app_metrics_timeline['active_threads'].append(app_resp.get('active_threads', 0))
            app_metrics_timeline['lock_contention_count'].append(app_resp.get('lock_contention_count', 0))
            app_metrics_timeline['requests_waiting'].append(app_resp.get('requests_waiting', 0))
            
            # Also poll proxy metrics
            proxy_resp = requests.get(f"{host}/proxy/metrics", timeout=1).json()
            proxy_metrics_timeline['timestamps'].append(time.time() - start_time)
            proxy_metrics_timeline['requests_in_queue'].append(proxy_resp.get('requests_in_queue', 0))
            proxy_metrics_timeline['proxy_overhead_count'].append(proxy_resp.get('proxy_overhead_count', 0))
            proxy_metrics_timeline['avg_queue_wait'].append(proxy_resp.get('avg_queue_wait_ms', 0))
            proxy_metrics_timeline['connection_errors'].append(proxy_resp.get('connection_errors', 0))
            proxy_metrics_timeline['retries'].append(proxy_resp.get('retries', 0))
        except:
            pass  # Skip if metrics unavailable
    
    start = time.time()
    try:
        r = requests.get(url, timeout=10)
        elapsed_ms = (time.time() - start) * 1000
        latencies.append(elapsed_ms)
        latency_timestamps.append(time.time() - start_time)  # Time since test started
        
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

# Calculate layer-specific percentiles and create visualization
if latencies:
    # Use actual measurements from headers, or use minimal values if not available
    # APPLICATION LAYER: upstream processing time from app server
    app_latencies = upstream_times if len(upstream_times) > 0 else [2.0] * len(latencies)
    
    # PROXY LAYER: proxy processing time (overhead)
    proxy_latencies = proxy_processing_times if len(proxy_processing_times) > 0 else [0.0] * len(latencies)
    
    # NETWORK LAYER: network delays
    net_latencies = network_delays if len(network_delays) > 0 else [0.0] * len(latencies)
    
    # Create comprehensive visualization: layer comparison + time series
    fig = plt.figure(figsize=(18, 14))
    
    # Top section: Layer comparison (3 bar charts)
    gs_top = fig.add_gridspec(1, 3, hspace=0.3, wspace=0.3, 
                              top=0.95, bottom=0.50, left=0.08, right=0.98)
    axes = [fig.add_subplot(gs_top[0, i]) for i in range(3)]
    
    layers = [
        ('APPLICATION LAYER', app_latencies, '#FF6B6B'),
        ('PROXY LAYER', proxy_latencies, '#4ECDC4'),
        ('NETWORK LAYER', net_latencies, '#95E1D3')
    ]
    
    for idx, (layer_name, layer_data, color) in enumerate(layers):
        ax = axes[idx]
        
        if layer_data and len(layer_data) > 0:
            p50_layer = np.percentile(layer_data, 50)
            p99_layer = np.percentile(layer_data, 99)
        else:
            p50_layer = 0
            p99_layer = 0
        
        # Bar chart for p50 and p99
        x_pos = [0, 1]
        bar1 = ax.bar(x_pos[0], p50_layer, color=color, alpha=0.6, edgecolor='black', linewidth=2)
        bar2 = ax.bar(x_pos[1], p99_layer, color=color, alpha=1.0, edgecolor='black', linewidth=2)
        
        ax.set_xticks(x_pos)
        ax.set_xticklabels(['p50', 'p99'])
        
        # Add value labels on bars
        ax.text(x_pos[0], p50_layer, f'{p50_layer:.2f}ms',
               ha='center', va='bottom', fontweight='bold', fontsize=11)
        ax.text(x_pos[1], p99_layer, f'{p99_layer:.2f}ms',
               ha='center', va='bottom', fontweight='bold', fontsize=11)
        
        ax.set_ylabel('Latency (ms)', fontsize=11, fontweight='bold')
        ax.set_title(layer_name, fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_ylim(bottom=0)
        
        # Highlight if p99 is significantly higher
        if p99_layer > p50_layer * 2:
            ax.set_facecolor('#fff5f5')
            ax.text(0.5, 0.95, 'HIGH p99', transform=ax.transAxes,
                   ha='center', va='top', fontsize=10, color='red', fontweight='bold',
                   bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.3))
    
    # Bottom section: Time-series graphs with SHARED X-AXIS for perfect correlation
    gs_bottom = fig.add_gridspec(5, 1, hspace=0.05, 
                                  top=0.45, bottom=0.05, left=0.10, right=0.95)
    
    # Calculate rolling percentiles (window size = 50 requests)
    window_size = 50
    times = []
    p50_over_time = []
    p99_over_time = []
    
    for i in range(window_size, len(latencies)):
        window = latencies[i-window_size:i]
        times.append(latency_timestamps[i])
        p50_over_time.append(np.percentile(window, 50))
        p99_over_time.append(np.percentile(window, 99))
    
    # Create 5 subplots sharing the same x-axis
    ax1 = fig.add_subplot(gs_bottom[0])  # Latency
    ax2 = fig.add_subplot(gs_bottom[1], sharex=ax1)  # Lock Contention
    ax3 = fig.add_subplot(gs_bottom[2], sharex=ax1)  # CPU Usage
    ax4 = fig.add_subplot(gs_bottom[3], sharex=ax1)  # Active Threads
    ax5 = fig.add_subplot(gs_bottom[4], sharex=ax1)  # Requests Waiting
    
    # Get max time for consistent x-axis
    max_time = max(times) if times else 1
    
    # 1. Latency over time (p50 vs p99)
    ax1.plot(times, p50_over_time, color='#4CAF50', linewidth=2.5, label='p50 (stable)', alpha=0.8)
    ax1.plot(times, p99_over_time, color='#F44336', linewidth=2.5, label='p99 (spikes)', alpha=0.8)
    ax1.fill_between(times, p50_over_time, p99_over_time, alpha=0.15, color='red')
    
    ax1.set_ylabel('Latency\n(ms)', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
    
    # Dynamic title based on mode
    if args.mode == "app":
        layer_title = "APPLICATION LAYER"
    elif args.mode == "proxy":
        layer_title = "PROXY LAYER"
    else:
        layer_title = "NETWORK LAYER"
    
    ax1.set_title(f'{layer_title}: Time-Aligned Diagnostic Metrics', fontsize=12, fontweight='bold', pad=10)
    ax1.legend(loc='upper right', fontsize=9, ncol=2)
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_xlim(0, max_time)
    plt.setp(ax1.get_xticklabels(), visible=False)
    
    # Choose which metrics to display based on mode
    if args.mode == "proxy":
        # PROXY MODE: Show proxy-specific metrics
        if len(proxy_metrics_timeline['timestamps']) > 0:
            # Calculate incremental proxy overhead events
            overhead_incremental = [0]
            for i in range(1, len(proxy_metrics_timeline['proxy_overhead_count'])):
                increment = proxy_metrics_timeline['proxy_overhead_count'][i] - proxy_metrics_timeline['proxy_overhead_count'][i-1]
                overhead_incremental.append(increment)
            
            # 2. Proxy Overhead Events
            ax2.bar(proxy_metrics_timeline['timestamps'], overhead_incremental, 
                    width=0.5, color='#4ECDC4', alpha=0.8, edgecolor='#008B8B', linewidth=1.5)
            
            # Add vertical lines to show correlation
            for idx, val in enumerate(overhead_incremental):
                if val > 0:
                    ax1.axvline(proxy_metrics_timeline['timestamps'][idx], color='cyan', alpha=0.15, linewidth=1.5, linestyle='--')
                    ax2.axvline(proxy_metrics_timeline['timestamps'][idx], color='cyan', alpha=0.15, linewidth=1.5, linestyle='--')
                    ax3.axvline(proxy_metrics_timeline['timestamps'][idx], color='cyan', alpha=0.15, linewidth=1.5, linestyle='--')
                    ax4.axvline(proxy_metrics_timeline['timestamps'][idx], color='cyan', alpha=0.15, linewidth=1.5, linestyle='--')
                    ax5.axvline(proxy_metrics_timeline['timestamps'][idx], color='cyan', alpha=0.15, linewidth=1.5, linestyle='--')
        
        ax2.set_ylabel('Proxy\nOverhead', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_xlim(0, max_time)
        plt.setp(ax2.get_xticklabels(), visible=False)
        
        # 3. Queue Depth (Requests Waiting in Proxy)
        if len(proxy_metrics_timeline['timestamps']) > 0:
            ax3.plot(proxy_metrics_timeline['timestamps'], proxy_metrics_timeline['requests_in_queue'], 
                    color='#FF9800', linewidth=2.5, marker='o', markersize=3)
            ax3.fill_between(proxy_metrics_timeline['timestamps'], 0, proxy_metrics_timeline['requests_in_queue'], 
                            alpha=0.3, color='#FF9800')
        
        ax3.set_ylabel('Queue\nDepth', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax3.grid(True, alpha=0.3, axis='y')
        ax3.set_xlim(0, max_time)
        plt.setp(ax3.get_xticklabels(), visible=False)
        
        # 4. Average Queue Wait Time
        if len(proxy_metrics_timeline['timestamps']) > 0:
            ax4.plot(proxy_metrics_timeline['timestamps'], proxy_metrics_timeline['avg_queue_wait'], 
                    color='#2196F3', linewidth=2.5, marker='s', markersize=3)
            ax4.fill_between(proxy_metrics_timeline['timestamps'], 0, proxy_metrics_timeline['avg_queue_wait'], 
                            alpha=0.3, color='#2196F3')
        
        ax4.set_ylabel('Avg Queue\nWait (ms)', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax4.grid(True, alpha=0.3, axis='y')
        ax4.set_xlim(0, max_time)
        plt.setp(ax4.get_xticklabels(), visible=False)
        
        # 5. Connection Errors
        if len(proxy_metrics_timeline['timestamps']) > 0:
            ax5.plot(proxy_metrics_timeline['timestamps'], proxy_metrics_timeline['connection_errors'], 
                    color='#9C27B0', linewidth=2.5, marker='^', markersize=3)
            ax5.fill_between(proxy_metrics_timeline['timestamps'], 0, proxy_metrics_timeline['connection_errors'], 
                            alpha=0.3, color='#9C27B0')
        
        ax5.set_ylabel('Connection\nErrors', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax5.set_xlabel('Time (seconds)', fontsize=11, fontweight='bold')
        ax5.grid(True, alpha=0.3, axis='y')
        ax5.set_xlim(0, max_time)
    
    elif args.mode == "network":
        # NETWORK MODE: Show network-specific metrics
        if len(proxy_metrics_timeline['timestamps']) > 0:
            # Calculate incremental retries (new retries since last poll)
            retries_incremental = [0]
            for i in range(1, len(proxy_metrics_timeline['retries'])):
                increment = proxy_metrics_timeline['retries'][i] - proxy_metrics_timeline['retries'][i-1]
                retries_incremental.append(increment)
            
            # 2. Network Retries/Retransmissions
            ax2.bar(proxy_metrics_timeline['timestamps'], retries_incremental, 
                    width=0.5, color='#95E1D3', alpha=0.8, edgecolor='#00A896', linewidth=1.5)
            
            # Add vertical lines to show correlation
            for idx, val in enumerate(retries_incremental):
                if val > 0:
                    ax1.axvline(proxy_metrics_timeline['timestamps'][idx], color='green', alpha=0.15, linewidth=1.5, linestyle='--')
                    ax2.axvline(proxy_metrics_timeline['timestamps'][idx], color='green', alpha=0.15, linewidth=1.5, linestyle='--')
                    ax3.axvline(proxy_metrics_timeline['timestamps'][idx], color='green', alpha=0.15, linewidth=1.5, linestyle='--')
                    ax4.axvline(proxy_metrics_timeline['timestamps'][idx], color='green', alpha=0.15, linewidth=1.5, linestyle='--')
                    ax5.axvline(proxy_metrics_timeline['timestamps'][idx], color='green', alpha=0.15, linewidth=1.5, linestyle='--')
        
        ax2.set_ylabel('Network\nRetries', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_xlim(0, max_time)
        plt.setp(ax2.get_xticklabels(), visible=False)
        
        # 3. Network Delay Variance (using rolling window)
        if len(network_delays) > 0:
            # Calculate rolling variance
            window = 20
            network_variance = []
            variance_times = []
            for i in range(window, len(network_delays)):
                window_data = network_delays[i-window:i]
                variance_times.append(latency_timestamps[i])
                network_variance.append(np.std(window_data))
            
            ax3.plot(variance_times, network_variance, 
                    color='#FF9800', linewidth=2.5, marker='o', markersize=3)
            ax3.fill_between(variance_times, 0, network_variance, 
                            alpha=0.3, color='#FF9800')
        
        ax3.set_ylabel('Network\nVariance', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax3.grid(True, alpha=0.3, axis='y')
        ax3.set_xlim(0, max_time)
        plt.setp(ax3.get_xticklabels(), visible=False)
        
        # 4. Connection Errors Over Time
        if len(proxy_metrics_timeline['timestamps']) > 0:
            ax4.plot(proxy_metrics_timeline['timestamps'], proxy_metrics_timeline['connection_errors'], 
                    color='#E53935', linewidth=2.5, marker='s', markersize=3)
            ax4.fill_between(proxy_metrics_timeline['timestamps'], 0, proxy_metrics_timeline['connection_errors'], 
                            alpha=0.3, color='#E53935')
        
        ax4.set_ylabel('Connection\nErrors', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax4.grid(True, alpha=0.3, axis='y')
        ax4.set_xlim(0, max_time)
        plt.setp(ax4.get_xticklabels(), visible=False)
        
        # 5. Network Delay (instantaneous)
        if len(network_delays) > 0 and len(latency_timestamps) == len(network_delays):
            ax5.plot(latency_timestamps, network_delays, 
                    color='#9C27B0', linewidth=1.5, alpha=0.6)
            ax5.fill_between(latency_timestamps, 0, network_delays, 
                            alpha=0.2, color='#9C27B0')
        
        ax5.set_ylabel('Network\nDelay (ms)', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax5.set_xlabel('Time (seconds)', fontsize=11, fontweight='bold')
        ax5.grid(True, alpha=0.3, axis='y')
        ax5.set_xlim(0, max_time)
    
    else:
        # APP MODE: Show application-specific metrics
        # 2. Lock Contention Events over time
        if len(app_metrics_timeline['timestamps']) > 0:
            # Calculate incremental lock contention (new events since last poll)
            contention_incremental = [0]
            for i in range(1, len(app_metrics_timeline['lock_contention_count'])):
                increment = app_metrics_timeline['lock_contention_count'][i] - app_metrics_timeline['lock_contention_count'][i-1]
                contention_incremental.append(increment)
            
            ax2.bar(app_metrics_timeline['timestamps'], contention_incremental, 
                    width=0.5, color='#FF6B6B', alpha=0.8, edgecolor='darkred', linewidth=1.5)
            
            # Add vertical lines to show correlation
            for idx, val in enumerate(contention_incremental):
                if val > 0:
                    ax1.axvline(app_metrics_timeline['timestamps'][idx], color='red', alpha=0.1, linewidth=1.5, linestyle='--')
                    ax2.axvline(app_metrics_timeline['timestamps'][idx], color='red', alpha=0.1, linewidth=1.5, linestyle='--')
                    ax3.axvline(app_metrics_timeline['timestamps'][idx], color='red', alpha=0.1, linewidth=1.5, linestyle='--')
                    ax4.axvline(app_metrics_timeline['timestamps'][idx], color='red', alpha=0.1, linewidth=1.5, linestyle='--')
                    ax5.axvline(app_metrics_timeline['timestamps'][idx], color='red', alpha=0.1, linewidth=1.5, linestyle='--')
        
        ax2.set_ylabel('Lock\nEvents', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.set_xlim(0, max_time)
        plt.setp(ax2.get_xticklabels(), visible=False)
        
        # 3. CPU Usage over time
        if len(app_metrics_timeline['timestamps']) > 0:
            ax3.plot(app_metrics_timeline['timestamps'], app_metrics_timeline['cpu_usage'], 
                    color='#FF9800', linewidth=2.5, marker='o', markersize=3)
            ax3.fill_between(app_metrics_timeline['timestamps'], 0, app_metrics_timeline['cpu_usage'], 
                            alpha=0.3, color='#FF9800')
        
        ax3.set_ylabel('CPU\n(%)', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax3.grid(True, alpha=0.3, axis='y')
        ax3.set_xlim(0, max_time)
        plt.setp(ax3.get_xticklabels(), visible=False)
        
        # 4. Active Threads over time
        if len(app_metrics_timeline['timestamps']) > 0:
            ax4.plot(app_metrics_timeline['timestamps'], app_metrics_timeline['active_threads'], 
                    color='#2196F3', linewidth=2.5, marker='s', markersize=3)
            ax4.fill_between(app_metrics_timeline['timestamps'], 
                            min(app_metrics_timeline['active_threads']) - 0.5,
                            app_metrics_timeline['active_threads'], 
                            alpha=0.3, color='#2196F3')
        
        ax4.set_ylabel('Active\nThreads', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax4.grid(True, alpha=0.3, axis='y')
        ax4.set_xlim(0, max_time)
        plt.setp(ax4.get_xticklabels(), visible=False)
        
        # 5. Requests Waiting (Blocked) over time
        if len(app_metrics_timeline['timestamps']) > 0:
            ax5.plot(app_metrics_timeline['timestamps'], app_metrics_timeline['requests_waiting'], 
                    color='#9C27B0', linewidth=2.5, marker='^', markersize=3)
            ax5.fill_between(app_metrics_timeline['timestamps'], 0, app_metrics_timeline['requests_waiting'], 
                            alpha=0.3, color='#9C27B0')
        
        ax5.set_ylabel('Blocked\nRequests', fontsize=10, fontweight='bold', rotation=0, ha='right', va='center')
        ax5.set_xlabel('Time (seconds)', fontsize=11, fontweight='bold')
        ax5.grid(True, alpha=0.3, axis='y')
        ax5.set_xlim(0, max_time)
    
    # Dynamic title based on mode
    if args.mode == "app":
        title = 'Tail Latency Diagnosis - Application Contention Metrics'
    elif args.mode == "proxy":
        title = 'Tail Latency Diagnosis - Proxy Overhead Metrics'
    else:
        title = 'Tail Latency Diagnosis - Network Variability Metrics'
    
    plt.suptitle(f'{title} (Mode: {args.mode.upper()})',
                fontsize=15, fontweight='bold', y=0.99)
    
    # Save the figure
    filename = f'layer_analysis_{args.mode}.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n[GRAPH] Saved as: {filename}")
    
    plt.show(block=False)
    plt.pause(0.1)

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
    print(f"  p99:   {p99:.2f} ms  [TAIL LATENCY]")
    print(f"  p99.9: {p99_9:.2f} ms")
    print(f"  max:   {max_lat:.2f} ms")
    
    # Calculate the delta between p99 and p50 (key metric!)
    p99_inflation = ((p99 - p50) / p50) * 100
    print(f"\nP99 Inflation: {p99_inflation:.1f}% above p50")
else:
    print("No successful requests.")

# Fetch and display layer-specific metrics
if args.analyze and latencies:
    print("\n" + "=" * 60)
    print("LAYER-SPECIFIC ANALYSIS")
    print("=" * 60)
    
    # Application metrics
    print("\n[APPLICATION LAYER METRICS]")
    try:
        app_metrics = requests.get("http://127.0.0.1:5000/metrics", timeout=2).json()
        print(f"  Total requests processed: {app_metrics['requests_total']}")
        print(f"  Lock contention events: {app_metrics['lock_contention_count']}")
        print(f"  Contention rate: {app_metrics['contention_rate']}%")
        print(f"  Avg processing time: {app_metrics['avg_processing_time_ms']:.2f} ms")
        
        wait_time = app_metrics['avg_wait_time_ms']
        if app_metrics['lock_contention_count'] > 0:
            if wait_time > 10:  # Only mark as HIGH if wait time is significant
                print(f"  Avg wait time (contended): {wait_time:.2f} ms  [HIGH]")
            else:
                print(f"  Avg wait time (contended): {wait_time:.2f} ms")
        else:
            print(f"  Avg wait time (contended): {wait_time:.2f} ms")
            
        print(f"  CPU usage: {app_metrics['cpu_percent']:.1f}%")
        print(f"  Active threads: {app_metrics['active_threads']}")
    except Exception as e:
        print(f"  [ERROR] Could not fetch app metrics: {e}")
    
    # Proxy metrics
    print("\n[PROXY LAYER METRICS]")
    try:
        proxy_metrics = requests.get(f"{host}/proxy/metrics", timeout=2).json()
        print(f"  Total requests: {proxy_metrics['requests_total']}")
        print(f"  Requests in queue: {proxy_metrics['requests_in_queue']}")
        print(f"  Avg queue wait: {proxy_metrics['avg_queue_wait_ms']:.2f} ms")
        print(f"  Proxy overhead events: {proxy_metrics['proxy_overhead_count']}")
        if proxy_metrics['proxy_overhead_count'] > 0:
            print(f"  Avg proxy processing: {proxy_metrics['avg_proxy_processing_ms']:.2f} ms  [HIGH]")
        print(f"  Connection errors: {proxy_metrics['connection_errors']}")
        print(f"  Upstream timeouts: {proxy_metrics['upstream_timeouts']}")
    except Exception as e:
        print(f"  [ERROR] Could not fetch proxy metrics: {e}")
    
    # Network metrics (from collected headers)
    print("\n[NETWORK LAYER METRICS]")
    if network_delays:
        network_p50 = np.percentile(network_delays, 50)
        network_p99 = np.percentile(network_delays, 99)
        print(f"  Network delay p50: {network_p50:.2f} ms")
        print(f"  Network delay p99: {network_p99:.2f} ms  [MONITORED]")
        print(f"  Retries: {proxy_metrics.get('retries', 0)}")
        
        if network_p99 > network_p50 * 5:
            print(f"  [WARNING] High network variability detected!")
    
    # DIAGNOSTIC SUMMARY
    print("\n" + "=" * 60)
    print("[DIAGNOSTIC SUMMARY]")
    print("=" * 60)
    
    if args.mode == "app":
        print("\n[ROOT CAUSE] APPLICATION-LAYER CONTENTION:")
        print(f"  * Contention rate: {app_metrics.get('contention_rate', 0)}%")
        print(f"  * Wait time for contended requests: {app_metrics.get('avg_wait_time_ms', 0):.2f} ms")
        print(f"  * p99 latency aligns with lock hold time (~100ms)")
        print(f"  * Proxy and network metrics show normal behavior")
        
    elif args.mode == "proxy":
        print("\n[ROOT CAUSE] PROXY OVERHEAD:")
        print(f"  * Proxy overhead events: {proxy_metrics.get('proxy_overhead_count', 0)}")
        print(f"  * Avg proxy processing time: {proxy_metrics.get('avg_proxy_processing_ms', 0):.2f} ms")
        print(f"  * p99 latency aligns with proxy delays (~50ms)")
        print(f"  * Application processing time remains stable")
        print(f"  * Network metrics show normal behavior")
        
    elif args.mode == "network":
        print("\n[ROOT CAUSE] NETWORK VARIABILITY:")
        print(f"  * Network retries: {proxy_metrics.get('retries', 0)}")
        print(f"  * Network p99 delay: {network_p99:.2f} ms")
        print(f"  * High variance in network layer measurements")
        print(f"  * Application and proxy metrics remain stable")
        print(f"  * p99 latency aligns with network spikes (60-150ms)")
    
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
