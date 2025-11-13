<img width="5202" height="4140" alt="image" src="https://github.com/user-attachments/assets/659315ed-6193-4df7-8a12-8036ad26c0bd" />

<img width="5248" height="4140" alt="image" src="https://github.com/user-attachments/assets/44293232-3a87-460a-832c-05a2bc0e3fd8" />

<img width="5248" height="4140" alt="image" src="https://github.com/user-attachments/assets/142ab95d-77f8-4d12-b0b2-26a331c8b543" />

<img width="5164" height="5376" alt="image" src="https://github.com/user-attachments/assets/2cb5a672-9f81-48a9-bca6-0ce6aade77d6" />


LATENCY RESULTS
Mode: mixed
Requests: 1000  |  Errors: 0

Percentiles:
- p50:   64.13 ms
- p95:   166.18 ms
- p99:   221.37 ms 
- p99.9: 310.64 ms
- max:   327.40 ms
- P99 Inflation: 245.2% above p50

APPLICATION LAYER METRICS
- Total requests processed: 1000
- Lock contention events: 47
- Contention rate: 4.7%
- Avg processing time: 7.27 ms
- Avg wait time (contended): 0.00 ms
- CPU usage: 9.2%
- Active threads: 2

PROXY LAYER METRICS
- Total requests: 1000
- Requests in queue: 0
- Avg queue wait: 13.54 ms
- Proxy overhead events: 48
- Avg proxy processing: 50.00 ms
- Connection errors: 0
- Upstream timeouts: 0

NETWORK LAYER METRICS
- Network delay p50: 2.00 ms
- Network delay p99: 150.00 ms  [MONITORED]
- Retries: 34
- [WARNING] High network variability detected!







