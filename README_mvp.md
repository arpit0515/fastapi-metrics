# FastAPI Metrics

**Zero-config metrics for FastAPI apps** - Perfect for solo developers and MVPs on single-instance deployments.

No Prometheus. No Grafana. No containers. Just simple metrics that work.

## Quick Start

```bash
pip install fastapi-metrics
```

```python
from fastapi import FastAPI
from fastapi_metrics import Metrics

app = FastAPI()

# One line to enable metrics
metrics = Metrics(app, storage="sqlite://metrics.db")

@app.post("/payment")
async def payment(amount: float, user_id: int):
    # Track custom business metrics
    await metrics.track("revenue", amount, user_id=user_id)
    return {"status": "ok"}
```

That's it. You now have:
- ✅ HTTP request tracking (latency, status codes, endpoints)
- ✅ Custom business metrics (revenue, signups, etc.)
- ✅ JSON query API for dashboards
- ✅ Automatic data retention

## Built-in API Endpoints

Once metrics are enabled, your app automatically gets:

```bash
GET  /metrics              # Current snapshot
GET  /metrics/query        # Time-series queries
GET  /metrics/endpoints    # Per-endpoint statistics
POST /metrics/cleanup      # Manual cleanup
```

### Example Queries

```bash
# Get all HTTP metrics from last 24 hours
GET /metrics/query?metric_type=http&from_hours=24

# Get revenue metrics grouped by hour
GET /metrics/query?metric_type=custom&name=revenue&group_by=hour

# Get per-endpoint stats
GET /metrics/endpoints
```

## Storage Options

### SQLite (Recommended)
Persistent storage, zero setup.

```python
metrics = Metrics(app, storage="sqlite://metrics.db")
```

### In-Memory
For testing/development.

```python
metrics = Metrics(app, storage="memory://")
```

## Tracking Custom Metrics

Track any business metric you care about:

```python
# Revenue tracking
await metrics.track("revenue", 99.99, user_id=123, plan="pro")

# User signups
await metrics.track("signups", 1, source="organic")

# Feature usage
await metrics.track("api_calls", 1, endpoint="/search")

# Any counter you want
await metrics.track("emails_sent", 1, campaign="welcome")
```

## Real-World Example

```python
from fastapi import FastAPI, HTTPException
from fastapi_metrics import Metrics

app = FastAPI()
metrics = Metrics(app, storage="sqlite://metrics.db", retention_hours=72)

@app.post("/api/search")
async def search(query: str, user_id: int):
    try:
        results = perform_search(query)
        await metrics.track("search_success", 1, user_id=user_id)
        return results
    except Exception as e:
        await metrics.track("search_error", 1, error=type(e).__name__)
        raise

@app.post("/api/payment")
async def payment(amount: float, user_id: int, plan: str):
    # Process payment...
    
    # Track business metrics
    await metrics.track("revenue", amount, user_id=user_id, plan=plan)
    await metrics.track("payment_count", 1, plan=plan)
    
    return {"status": "success"}
```

## Use with Retool/Bubble/No-Code Tools

The metrics API returns JSON, making it easy to build dashboards:

```javascript
// In Retool, create a REST API query:
GET https://your-api.com/metrics/query?metric_type=custom&name=revenue&group_by=hour

// Use the response to populate charts
{{query1.data.results}}
```

## Configuration

```python
Metrics(
    app,
    storage="sqlite://metrics.db",  # Storage backend
    retention_hours=24,              # How long to keep data
    enable_cleanup=True,             # Auto-cleanup old data
)
```

## What Gets Tracked Automatically

Every HTTP request records:
- Endpoint path
- HTTP method
- Status code
- Response time (ms)
- Timestamp

## Query Examples

### Get HTTP metrics from last 6 hours
```bash
GET /metrics/query?metric_type=http&from_hours=6&to_hours=0
```

### Get revenue by hour for last 24 hours
```bash
GET /metrics/query?metric_type=custom&name=revenue&group_by=hour&from_hours=24
```

### Get stats for specific endpoint
```bash
GET /metrics/query?metric_type=http&endpoint=/api/payment&from_hours=24
```

### Get per-endpoint performance
```bash
GET /metrics/endpoints
```

Response:
```json
{
  "endpoints": [
    {
      "endpoint": "/api/payment",
      "method": "POST",
      "count": 1234,
      "avg_latency_ms": 45.6,
      "error_rate": 0.02
    }
  ]
}
```

## Target Use Cases

Perfect for:
- ✅ Solo developers building MVPs
- ✅ Side projects and prototypes
- ✅ Single-server deployments (VPS, EC2)
- ✅ Apps without DevOps resources
- ✅ Local development and testing

**Not designed for:**
- ❌ Kubernetes multi-pod deployments (use Phase 2 with Redis)
- ❌ Distributed systems (coming in Phase 2)
- ❌ High-scale production (use Prometheus/Grafana)

## Performance

- < 1ms overhead per request
- Async storage operations (non-blocking)
- Automatic cleanup of old data
- Indexed queries for fast retrieval

## Requirements

- Python 3.8+
- FastAPI 0.100.0+

## Installation

```bash
pip install fastapi-metrics
```

For development:
```bash
git clone https://github.com/arpit0515/fastapi-metrics
cd fastapi-metrics
pip install -e ".[dev]"
pytest
```

## Roadmap

### ✅ Phase 1 (Current)
- HTTP request tracking
- SQLite & in-memory storage
- Custom business metrics
- Query API

### 🚧 Phase 2 (Planned)
- Redis storage for multi-instance deployments
- Kubernetes health checks (`/health/live`, `/health/ready`)
- System metrics (CPU, memory, disk)
- LLM cost tracking (OpenAI, Anthropic)

### 🔮 Phase 3 (Future)
- Prometheus export format
- Basic alerting (webhooks)
- Data aggregation for long-term storage

## Contributing

Contributions welcome! This is an early-stage project focused on simplicity.

## License

MIT License - see LICENSE file

## Support

- 🐛 Issues: https://github.com/arpit0515/fastapi-metrics/issues
- 💬 Discussions: https://github.com/arpit0515/fastapi-metrics/discussions

---

Made for developers who want metrics without the infrastructure overhead.