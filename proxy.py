# proxy.py
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests, urllib.parse, random, time, threading, os, json
from collections import deque

UPSTREAM = os.environ.get("SERVER", "http://127.0.0.1:5000")

# Proxy metrics
proxy_metrics = {
    "requests_total": 0,
    "requests_in_queue": 0,
    "queue_wait_times": deque(maxlen=1000),
    "proxy_processing_times": deque(maxlen=1000),
    "proxy_overhead_count": 0,
    "network_delays": deque(maxlen=1000),
    "connection_errors": 0,
    "retries": 0,
    "upstream_timeouts": 0,
}
proxy_lock = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default logging
        pass
    
    def do_GET(self):
        global proxy_metrics
        
        request_start = time.time()
        
        # Special endpoints for proxy metrics
        if self.path == "/proxy/metrics":
            self.serve_proxy_metrics()
            return
        elif self.path == "/proxy/metrics/reset":
            self.reset_proxy_metrics()
            return
        
        # parse query params, keep 'mode' param and forward it
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        mode = qs.get("mode", ["none"])[0]
        
        # Track queue entry
        with proxy_lock:
            proxy_metrics["requests_in_queue"] += 1
        
        queue_start = time.time()
        proxy_delay = 0.0
        network_delay = 0.0
        
        # Simulate proxy overhead (mode=proxy): 5% of requests get 50ms delay
        # This represents proxy CPU saturation, config parsing, routing logic
        if mode == "proxy":
            if random.random() < 0.05:
                proxy_delay = 0.05
                time.sleep(proxy_delay)  # 50 ms proxy-induced delay
                with proxy_lock:
                    proxy_metrics["proxy_overhead_count"] += 1

        # Simulate network variability (mode=network): random jitter/packet loss
        if mode == "network":
            # Small probability of big jitter and small probability of medium jitter
            r = random.random()
            if r < 0.02:
                network_delay = 0.15   # 150ms spike (packet loss, retransmission)
                time.sleep(network_delay)
                with proxy_lock:
                    proxy_metrics["retries"] += 1
            elif r < 0.07:
                network_delay = 0.06   # 60ms jitter (congestion)
                time.sleep(network_delay)
            else:
                network_delay = 0.002  # base small delay
                time.sleep(network_delay)
        
        queue_wait = time.time() - queue_start
        
        # Track that we're processing (out of queue)
        with proxy_lock:
            proxy_metrics["requests_in_queue"] -= 1
            proxy_metrics["requests_total"] += 1
            proxy_metrics["queue_wait_times"].append(queue_wait * 1000)
            if proxy_delay > 0:
                proxy_metrics["proxy_processing_times"].append(proxy_delay * 1000)
            if network_delay > 0:
                proxy_metrics["network_delays"].append(network_delay * 1000)
        
        # Forward request to upstream app, preserving mode param
        upstream_url = UPSTREAM + parsed.path + ("?" + parsed.query if parsed.query else "")
        try:
            upstream_start = time.time()
            resp = requests.get(upstream_url, timeout=5)
            upstream_time = time.time() - upstream_start
            
            body = resp.content
            self.send_response(resp.status_code)
            
            # Add proxy timing headers for observability
            self.send_header("X-Proxy-Queue-Wait-Ms", f"{queue_wait * 1000:.2f}")
            self.send_header("X-Proxy-Processing-Ms", f"{proxy_delay * 1000:.2f}")
            self.send_header("X-Network-Delay-Ms", f"{network_delay * 1000:.2f}")
            self.send_header("X-Upstream-Time-Ms", f"{upstream_time * 1000:.2f}")
            
            for k, v in resp.headers.items():
                # skip hop-by-hop headers
                if k.lower() not in ("connection","keep-alive","proxy-authenticate","proxy-authorization","te","trailers","transfer-encoding","upgrade"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
        except requests.Timeout:
            with proxy_lock:
                proxy_metrics["upstream_timeouts"] += 1
            self.send_response(504)
            self.end_headers()
            self.wfile.write(b"Gateway Timeout")
        except requests.RequestException as e:
            with proxy_lock:
                proxy_metrics["connection_errors"] += 1
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(e).encode())
    
    def serve_proxy_metrics(self):
        """Serve proxy metrics"""
        with proxy_lock:
            avg_queue_wait = (sum(proxy_metrics["queue_wait_times"]) / len(proxy_metrics["queue_wait_times"])
                             if proxy_metrics["queue_wait_times"] else 0)
            avg_proxy_processing = (sum(proxy_metrics["proxy_processing_times"]) / len(proxy_metrics["proxy_processing_times"])
                                   if proxy_metrics["proxy_processing_times"] else 0)
            avg_network_delay = (sum(proxy_metrics["network_delays"]) / len(proxy_metrics["network_delays"])
                                if proxy_metrics["network_delays"] else 0)
            
            metrics_data = {
                "requests_total": proxy_metrics["requests_total"],
                "requests_in_queue": proxy_metrics["requests_in_queue"],
                "avg_queue_wait_ms": round(avg_queue_wait, 2),
                "proxy_overhead_count": proxy_metrics["proxy_overhead_count"],
                "avg_proxy_processing_ms": round(avg_proxy_processing, 2),
                "avg_network_delay_ms": round(avg_network_delay, 2),
                "connection_errors": proxy_metrics["connection_errors"],
                "retries": proxy_metrics["retries"],
                "upstream_timeouts": proxy_metrics["upstream_timeouts"],
            }
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(metrics_data).encode())
    
    def reset_proxy_metrics(self):
        """Reset proxy metrics"""
        global proxy_metrics
        with proxy_lock:
            proxy_metrics = {
                "requests_total": 0,
                "requests_in_queue": 0,
                "queue_wait_times": deque(maxlen=1000),
                "proxy_processing_times": deque(maxlen=1000),
                "proxy_overhead_count": 0,
                "network_delays": deque(maxlen=1000),
                "connection_errors": 0,
                "retries": 0,
                "upstream_timeouts": 0,
            }
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "reset"}).encode())

def run(server_class=HTTPServer, handler_class=Handler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Proxy listening on :{port}, forwarding to {UPSTREAM}")
    print(f"Proxy metrics available at http://127.0.0.1:{port}/proxy/metrics")
    httpd.serve_forever()

if __name__ == "__main__":
    port = int(os.environ.get("PROXY_PORT", "8080"))
    run(port=port)
