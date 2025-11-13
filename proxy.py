# proxy.py
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests, urllib.parse, random, time, threading

UPSTREAM = "http://127.0.0.1:5000"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # parse query params, keep 'mode' param and forward it
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        mode = qs.get("mode", ["none"])[0]

        # Simulate proxy overhead (mode=proxy): 5% of requests get 50ms delay
        if mode == "proxy":
            if random.random() < 0.05:
                time.sleep(0.05)  # 50 ms proxy-induced delay

        # Simulate network variability (mode=network): random jitter on every request
        if mode == "network":
            # Small probability of big jitter and small probability of medium jitter
            r = random.random()
            if r < 0.02:
                time.sleep(0.15)   # 150ms spike
            elif r < 0.07:
                time.sleep(0.06)   # 60ms jitter
            else:
                time.sleep(0.002)  # base small delay

        # Forward request to upstream app, preserving mode param
        upstream_url = UPSTREAM + parsed.path + ("?" + parsed.query if parsed.query else "")
        try:
            resp = requests.get(upstream_url, timeout=5)
            body = resp.content
            self.send_response(resp.status_code)
            for k, v in resp.headers.items():
                # skip hop-by-hop headers
                if k.lower() not in ("connection","keep-alive","proxy-authenticate","proxy-authorization","te","trailers","transfer-encoding","upgrade"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
        except requests.RequestException as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(e).encode())

def run(server_class=HTTPServer, handler_class=Handler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Proxy listening on :{port}, forwarding to {UPSTREAM}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
