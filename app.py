# app.py
from flask import Flask, request
import threading, time, random

app = Flask(__name__)
lock = threading.Lock()

#  Application with contention lock

@app.route("/work")
def work():
    # mode is passed from proxy as query param
    mode = request.args.get("mode", "none")
    # Normal small processing time
    base = 0.002

    if mode == "app":
        # 5% requests hit a lock and sleep to simulate contention
        if random.random() < 0.05:
            with lock:
                time.sleep(0.1)   # heavy blocking
        else:
            time.sleep(base)
    else:
        time.sleep(base)
    return "done", 200

if __name__ == "__main__":
    # Use 5000 for the app; proxy will forward to this
    app.run(host="0.0.0.0", port=5000, threaded=True)
