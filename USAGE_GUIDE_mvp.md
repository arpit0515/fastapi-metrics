# FastAPI Metrics - Usage Guide

## Quick Start (30 seconds)

```bash
pip install fastapi-metrics
```

```python
from fastapi import FastAPI
from fastapi_metrics import Metrics

app = FastAPI()
metrics = Metrics(app, storage="sqlite://metrics.db")

# That's it! Metrics are now tracking.
```

## Storage Options

### SQLite (Default - Recommended)
```python
metrics = Metrics(app, storage="sqlite://metrics.db")
```

### In-Memory (Testing/Dev)
```python
metrics = Metrics(app, storage="memory://")
```

## Full Configuration

```python
metrics = Metrics(
    app,
    storage="sqlite://metrics.db",  # Storage backend
    retention_hours=24,              # Keep data for 24 hours
    enable_cleanup=True,             # Auto-cleanup old data
)
```

## Tracking Custom Metrics

```python
@app.post("/payment")
async def payment(amount: float, user_id: int, plan: str):
    # Your payment logic here...
    
    # Track business metrics
    await metrics.track("revenue", amount, user_id=user_id, plan=plan)
    await metrics.track("payment_count", 1, plan=plan)
    
    return {"status": "success"}

@app.post("/signup")
async def signup(email: str, source: str = "organic"):
    # Your signup logic...
    
    await metrics.track("signups", 1, source=source)
    await metrics.track("users_total", 1)
    
    return {"email": email}

@app.get("/api/search")
async def search(query: str):
    try:
        results = perform_search(query)
        await metrics.track("search_success", 1)
        return results
    except Exception as e:
        await metrics.track("search_error", 1, error_type=type(e).__name__)
        raise
```

## Built-in API Endpoints

Your app automatically gets these endpoints:

### 1. Current Snapshot
```bash
GET /metrics
```
Response:
```json
{
  "active_requests": 3,
  "timestamp": "2025-12-10T10:30:00"
}
```

### 2. Query HTTP Metrics
```bash
# Last 24 hours
GET /metrics/query?metric_type=http&from_hours=24

# Specific endpoint
GET /metrics/query?metric_type=http&endpoint=/api/payment&from_hours=6

# Grouped by hour
GET /metrics/query?metric_type=http&group_by=hour&from_hours=12
```

### 3. Query Custom Metrics
```bash
# All revenue metrics
GET /metrics/query?metric_type=custom&name=revenue&from_hours=24

# Revenue grouped by hour
GET /metrics/query?metric_type=custom&name=revenue&group_by=hour&from_hours=24

# All custom metrics
GET /metrics/query?metric_type=custom&from_hours=6
```

### 4. Endpoint Statistics
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
      "min_latency_ms": 12.3,
      "max_latency_ms": 890.2,
      "error_rate": 0.02
    }
  ]
}
```

### 5. Manual Cleanup
```bash
POST /metrics/cleanup?hours_to_keep=24
```

## Complete Example App

```python
from fastapi import FastAPI, HTTPException
from fastapi_metrics import Metrics
import uvicorn

app = FastAPI(title="My SaaS API")

# Initialize metrics
metrics = Metrics(
    app,
    storage="sqlite://metrics.db",
    retention_hours=72,  # Keep 3 days of data
)

@app.get("/")
async def root():
    return {"message": "API is running"}

@app.post("/api/users")
async def create_user(email: str, plan: str = "free"):
    # Your user creation logic...
    user_id = 123  # From your DB
    
    # Track metrics
    await metrics.track("signups", 1, plan=plan)
    await metrics.track("users_total", 1)
    
    return {"user_id": user_id, "email": email}

@app.post("/api/payment")
async def process_payment(user_id: int, amount: float, plan: str):
    try:
        # Your payment processing...
        
        # Track success
        await metrics.track("revenue", amount, user_id=user_id, plan=plan)
        await metrics.track("payment_success", 1, plan=plan)
        
        return {"status": "success", "amount": amount}
    
    except Exception as e:
        # Track failures
        await metrics.track("payment_failed", 1, error=type(e).__name__)
        raise HTTPException(status_code=500, detail="Payment failed")

@app.get("/api/search")
async def search(query: str, user_id: int):
    # Track search usage
    await metrics.track("searches", 1, user_id=user_id)
    
    results = perform_search(query)
    
    if not results:
        await metrics.track("search_no_results", 1)
    
    return {"results": results}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Testing Your Setup

1. **Start your app:**
   ```bash
   uvicorn your_app:app --reload
   ```

2. **Make some requests:**
   ```bash
   curl http://localhost:8000/
   curl -X POST "http://localhost:8000/api/payment?user_id=1&amount=99.99&plan=pro"
   ```

3. **Check metrics:**
   ```bash
   # Current snapshot
   curl http://localhost:8000/metrics
   
   # HTTP metrics
   curl "http://localhost:8000/metrics/query?metric_type=http&from_hours=1"
   
   # Custom metrics
   curl "http://localhost:8000/metrics/query?metric_type=custom&name=revenue&from_hours=1"
   
   # Endpoint stats
   curl http://localhost:8000/metrics/endpoints
   ```

## Common Patterns

### Track API Usage Per User
```python
@app.get("/api/data")
async def get_data(user_id: int, endpoint: str):
    await metrics.track("api_calls", 1, user_id=user_id, endpoint=endpoint)
    # Your logic...
```

### Track Feature Usage
```python
@app.post("/api/feature/export")
async def export_data(user_id: int, format: str):
    await metrics.track("feature_export", 1, user_id=user_id, format=format)
    # Your logic...
```

### Track Errors by Type
```python
try:
    # Your code...
except ValueError as e:
    await metrics.track("errors", 1, type="validation")
except DatabaseError as e:
    await metrics.track("errors", 1, type="database")
```

## Integration with Dashboards

### Retool Example
1. Create REST API query in Retool
2. Set URL: `https://your-api.com/metrics/query?metric_type=custom&name=revenue&group_by=hour&from_hours=24`
3. Use `{{query1.data.results}}` in chart components

### Custom Dashboard
```javascript
// Fetch revenue data
fetch('/metrics/query?metric_type=custom&name=revenue&group_by=hour&from_hours=24')
  .then(r => r.json())
  .then(data => {
    // data.results contains hourly revenue
    renderChart(data.results);
  });
```

## What Gets Tracked Automatically

Without any code changes, every HTTP request records:
- Endpoint path
- HTTP method (GET, POST, etc.)
- Status code
- Response time in milliseconds
- Timestamp

Access via: `GET /metrics/query?metric_type=http`

## Tips

1. **Use descriptive metric names**: `"user_signups"` not `"metric1"`
2. **Add context with labels**: `await metrics.track("error", 1, type="timeout")`
3. **Track both success and failure**: Don't just track happy paths
4. **Keep labels low-cardinality**: Avoid unique IDs as label values for aggregation
5. **Query regularly**: Set up cron jobs to export data for long-term storage

## Troubleshooting

**Metrics not showing up?**
- Ensure `await metrics.track()` is called (it's async)
- Check storage is initialized (automatic on app startup)

**Storage file growing too large?**
- Reduce `retention_hours`
- Call `/metrics/cleanup` more frequently
- Consider exporting old data before cleanup

**Slow queries?**
- SQLite has indexes on timestamp/endpoint/name
- Limit query time ranges
- Use `group_by=hour` for aggregated data
