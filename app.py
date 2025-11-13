# app.py
from flask import Flask, request, jsonify
import threading, time, random, os, psutil

app = Flask(__name__)
lock = threading.Lock()

# Metrics collection
metrics = {
    "requests_total": 0,
    "requests_waiting": 0,
    "lock_contention_count": 0,
    "total_processing_time": 0.0,
    "total_wait_time": 0.0,
}
metrics_lock = threading.Lock()

@app.route("/work")
def work():
    global metrics
    
    # Record request arrival
    arrival_time = time.time()
    mode = request.args.get("mode", "none")
    base = 0.002
    
    # Measure CPU before processing
    cpu_before = psutil.cpu_percent(interval=0.01)
    
    # Track waiting (for application contention scenario)
    wait_time = 0.0
    processing_start = time.time()
    
    if mode == "app" or mode == "mixed":
        # 5% requests hit a lock and sleep to simulate contention (app mode)
        # 5% for mixed mode as well (realistic)
        contention_rate = 0.05
        
        if random.random() < contention_rate:
            with metrics_lock:
                metrics["requests_waiting"] += 1
            
            # This simulates waiting for a shared resource (database, cache, etc.)
            wait_start = time.time()
            with lock:
                wait_time = time.time() - wait_start
                with metrics_lock:
                    metrics["lock_contention_count"] += 1
                    metrics["total_wait_time"] += wait_time
                time.sleep(0.1)   # heavy blocking work
            
            with metrics_lock:
                metrics["requests_waiting"] -= 1
        else:
            time.sleep(base)
    else:
        time.sleep(base)
    
    # Calculate processing time
    processing_time = time.time() - processing_start
    
    # Measure CPU after processing
    cpu_after = psutil.cpu_percent(interval=0.01)
    
    # Update metrics
    with metrics_lock:
        metrics["requests_total"] += 1
        metrics["total_processing_time"] += processing_time
    
    # Return metrics with response (for debugging)
    response_data = {
        "status": "done",
        "processing_time_ms": round(processing_time * 1000, 2),
        "wait_time_ms": round(wait_time * 1000, 2),
        "cpu_delta": round(cpu_after - cpu_before, 2)
    }
    
    return jsonify(response_data), 200

@app.route("/metrics")
def get_metrics():
    """Endpoint to retrieve application metrics"""
    with metrics_lock:
        avg_processing = (metrics["total_processing_time"] / metrics["requests_total"] 
                         if metrics["requests_total"] > 0 else 0)
        avg_wait = (metrics["total_wait_time"] / metrics["lock_contention_count"] 
                   if metrics["lock_contention_count"] > 0 else 0)
        
        return jsonify({
            "requests_total": metrics["requests_total"],
            "requests_waiting": metrics["requests_waiting"],
            "lock_contention_count": metrics["lock_contention_count"],
            "contention_rate": round(metrics["lock_contention_count"] / metrics["requests_total"] * 100, 2) 
                               if metrics["requests_total"] > 0 else 0,
            "avg_processing_time_ms": round(avg_processing * 1000, 2),
            "avg_wait_time_ms": round(avg_wait * 1000, 2),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "active_threads": threading.active_count()
        })

@app.route("/metrics/reset")
def reset_metrics():
    """Reset metrics for a fresh test"""
    global metrics
    with metrics_lock:
        metrics = {
            "requests_total": 0,
            "requests_waiting": 0,
            "lock_contention_count": 0,
            "total_processing_time": 0.0,
            "total_wait_time": 0.0,
        }
    return jsonify({"status": "reset"}), 200

if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "0.0.0.0")
    port = int(os.environ.get("APP_PORT", "5000"))
    print(f"Application server starting on {host}:{port}")
    print(f"Metrics available at http://{host}:{port}/metrics")
    app.run(host=host, port=port, threaded=True)
