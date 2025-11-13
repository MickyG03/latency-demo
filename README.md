# Tail Latency Diagnosis Demo

A hands-on demonstration of how to diagnose tail latency issues when **p50 is stable but p99 is inflated** by comparing signal deltas across system layers.

## 🎯 What This Demo Does

When p99 latency spikes but p50 remains stable, it means a small percentage of requests are significantly slower. This demo shows how to identify whether the root cause is:

1. **Application-layer contention** (lock contention, CPU saturation, blocked threads)
2. **Service-mesh proxy overhead** (routing delays, queue buildup, config overhead)
3. **Network variability** (packet loss, retries, congestion, jitter)

### The Key Principle

> **Compare metrics across layers. The layer with metric deltas temporally correlated to p99 spikes while other layers remain stable is the root cause.**

## 🏗️ Architecture

```
Client (client.py) → Proxy (port 8080) → Application (port 5000)
                      ↓
            Collects metrics from all layers
                      ↓
        Generates time-aligned visualizations
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the Services

**Terminal 1 - Application Server:**
```bash
python app.py
```

**Terminal 2 - Service Mesh Proxy:**
```bash
python proxy.py
```

### 3. Run Diagnostic Tests

**Terminal 3 - Run Client:**

```bash
# Test individual scenarios
python client.py --mode app --n 1000 --analyze
python client.py --mode proxy --n 1000 --analyze
python client.py --mode network --n 1000 --analyze

# Test realistic mixed scenario (multiple layers have issues)
python client.py --mode mixed --n 1000 --analyze
```
