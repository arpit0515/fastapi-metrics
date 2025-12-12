# FastAPI Metrics - Project Specification

## Project Vision
Zero-config metrics and observability for FastAPI apps targeting indie devs, startups, and no-code platforms. No Prometheus/Grafana infrastructure required.

## Core Value Proposition
- **5-minute setup**: One import, one line of code
- **No infrastructure**: SQLite/memory storage, no containers
- **Business metrics**: Track revenue, users, features - not just HTTP metrics
- **Query API**: JSON endpoints for custom dashboards
- **Cost tracking**: Auto-detect OpenAI/Anthropic API costs
- **No-code ready**: Retool/Bubble can consume the API directly

---

## Target Users
1. Indie developers building MVPs
2. Early-stage startups (pre-Series A)
3. No-code platform backends (Bubble, Retool, Make.com)
4. Developers prototyping without DevOps resources

---

## Technical Architecture

### Package Structure
```
fastapi-metrics/
├── fastapi_metrics/
│   ├── __init__.py
│   ├── core.py              # Main Metrics class
│   ├── middleware.py        # Request tracking middleware
│   ├── storage/
│   │   ├── base.py          # Storage interface
│   │   ├── memory.py        # In-memory storage
│   │   ├── sqlite.py        # SQLite storage
│   │   └── redis.py         # Redis storage (optional)
│   ├── collectors/
│   │   ├── http.py          # HTTP request metrics
│   │   ├── system.py        # CPU, memory, disk
│   │   ├── business.py      # Custom business metrics
│   │   └── cost.py          # LLM API cost tracking
│   ├── health/
│   │   ├── checks.py        # Health check implementations
│   │   └── endpoints.py     # Health endpoints
│   ├── query.py             # Metrics query engine
│   └── exporters/
│       ├── json.py          # JSON export
│       ├── prometheus.py    # Prometheus format
│       └── csv.py           # CSV export
├── tests/
├── examples/
├── docs/
└── pyproject.toml
```

---

## Phase 1: Core Functionality ⏳

### 1.1 Basic Setup & Middleware
- ✅ Main `Metrics` class initialization
- ✅ FastAPI app integration
- ✅ Request tracking middleware
- ✅ Response time calculation
- ✅ Status code tracking

### 1.2 Storage Backends
- ✅ Abstract storage interface
- ✅ In-memory storage (dict-based)
- ✅ SQLite storage with tables:
  - `http_requests` (timestamp, endpoint, method, status, latency_ms)
  - `custom_metrics` (timestamp, metric_name, value, labels)
  - `system_metrics` (timestamp, cpu, memory, disk)

### 1.3 HTTP Metrics Collection
- ✅ Requests per endpoint
- ✅ Requests per status code
- ✅ Requests per method
- ✅ Latency percentiles (p50, p95, p99)
- ✅ Error rate calculation
- ✅ Active requests counter

### 1.4 Query API Endpoints
- ✅ `GET /metrics` - Current snapshot (JSON)
- ✅ `GET /metrics/query` - Time-series queries
  - Query params: `from`, `to`, `metric`, `group_by`, `endpoint`
- ✅ `GET /metrics/endpoints` - Per-endpoint stats
- ✅ `GET /metrics/export?format=csv|prometheus`

**Deliverable**: Basic HTTP metrics with SQLite storage and query API

---

## Phase 2: Health Checks & System Metrics ⏳

### 2.1 Health Check System
- ✅ Health check base class
- ✅ Built-in checks:
  - ✅ Database connectivity
  - ✅ Redis connectivity
  - ✅ Disk space
  - ✅ Memory usage
  - ✅ Custom check support
- ✅ Health endpoints:
  - ✅ `GET /health` - Simple status
  - ✅ `GET /health/live` - Liveness probe
  - ✅ `GET /health/ready` - Readiness probe with checks

### 2.2 System Metrics
- ✅ CPU usage tracking
- ✅ Memory usage tracking
- ✅ Disk usage tracking
- ✅ Uptime tracking
- ✅ System metrics endpoint

### 2.3 Additional
- ✅Make Redis storage first-class (not optional)
- ✅ Add proper K8s health checks (Phase 2 should be Phase 1)
- ✅ Add deployment examples for multi-instance setups
- ✅ Position as "lightweight alternative to Prometheus that scales"

**Deliverable**: Production-ready health checks for Kubernetes

---

## Phase 3: Business Metrics & Cost Tracking ⏳

### 3.1 Custom Business Metrics
- ✅ `metrics.track(name, value, **labels)` API
- ✅ Counter metrics
- ✅ Gauge metrics
- ✅ Histogram metrics
- ✅ Label/tag support for segmentation

### 3.2 LLM Cost Tracking
- ✅ Auto-detect OpenAI API calls
- ✅ Auto-detect Anthropic API calls
- ✅ Token usage tracking
- ✅ Cost calculation (using current pricing)
- ✅ Cost by model/endpoint
- ✅ `GET /metrics/costs` endpoint

**Deliverable**: Track custom business KPIs and LLM costs

---

## Phase 4: Advanced Features ⏳

### 4.1 Retention & Cleanup
- [ ] Configurable retention period
- [ ] Automatic data cleanup job
- [ ] Aggregation for old data (hourly → daily)

### 4.2 Alerting (Simple)
- [ ] Threshold-based alerts
- [ ] Webhook notifications
- [ ] Email notifications (optional)

### 4.3 Export Formats
- [ ] Prometheus format
- [ ] CSV export
- [ ] JSON export with timestamps

**Deliverable**: Production-grade data management

---

## Phase 5: Documentation & Examples ⏳

### 5.1 Documentation
- [ ] README with quick start
- [ ] Full API documentation
- [ ] Configuration guide
- [ ] Storage backend comparison
- [ ] Kubernetes deployment guide

### 5.2 Examples
- [ ] Basic FastAPI app
- [ ] With database health checks
- [ ] Custom business metrics
- [ ] LLM cost tracking
- [ ] Retool integration example
- [ ] No-code tool integration guide

### 5.3 Testing
- [ ] Unit tests (80%+ coverage)
- [ ] Integration tests
- [ ] Performance benchmarks

**Deliverable**: Production-ready library with docs

---

## API Design (MVP)

### Basic Usage
```python
from fastapi import FastAPI
from fastapi_metrics import Metrics

app = FastAPI()

# Minimal setup
metrics = Metrics(
    app,
    storage="sqlite://metrics.db",  # or "memory://"
    retention_hours=24,
)

# Track custom metrics anywhere
@app.post("/payment")
def payment(amount: float, user_id: int):
    metrics.track("revenue", amount, user_id=user_id)
    metrics.track("payment_count", 1)
    return {"status": "ok"}
```

### Query Examples
```
GET /metrics
GET /metrics/query?metric=revenue&from=24h&group_by=hour
GET /metrics/endpoints
GET /metrics/costs
GET /health/ready
```

---

## Key Decisions

### Storage Strategy
- **Default**: SQLite (single file, no setup)
- **Optional**: Redis (for distributed systems)
- **Fallback**: In-memory (testing/development)

### Data Model
- Store raw events initially
- Aggregate on query (Phase 1)
- Pre-aggregate for performance (Phase 4)

### Performance
- Async middleware (non-blocking)
- Background workers for aggregation
- Configurable batch writes
- Query result caching

---

## Success Metrics
- [ ] < 5 lines of code to set up
- [ ] < 1ms overhead per request
- [ ] Works with SQLite (no external deps)
- [ ] Query API returns in < 100ms
- [ ] Retool/Bubble integration works out-of-box

---

## Non-Goals (v1)
- ❌ Replace Prometheus/Grafana for large scale
- ❌ Distributed tracing
- ❌ Log aggregation
- ❌ APM-level profiling
- ❌ Built-in UI (JSON API only)

---

## Dependencies (Keep Minimal)
```toml
[dependencies]
fastapi = ">=0.100.0"
pydantic = ">=2.0.0"
aiosqlite = ">=0.19.0"  # Async SQLite
psutil = ">=5.9.0"      # System metrics
httpx = ">=0.24.0"      # For health checks (optional)
```

---

## Progress Tracker

### ✅ Completed
- Project planning
- Architecture design

### 🚧 In Progress
- None

### ⏳ Todo
- Phase 1: Core functionality
- Phase 2: Health checks
- Phase 3: Business metrics
- Phase 4: Advanced features
- Phase 5: Documentation

---

## Quick Start Command (Future)
```bash
pip install fastapi-metrics
```

## Development Setup (Future)
```bash
git clone https://github.com/yourusername/fastapi-metrics
cd fastapi-metrics
poetry install
poetry run pytest
```

---

## Notes & Decisions Log
- 2025-12-10: Initial spec created
- Target: Indie devs who want metrics without infrastructure
- Focus: Simplicity over enterprise features
- SQLite as default storage for zero-config experience

---

## 🧩 Advanced Considerations & Good-to-Have Enhancements

This project aims to provide simple, zero-config metrics for small applications, but as usage grows, there are several important operational considerations worth keeping in mind. These are not required for most small projects, but they become valuable as traffic increases or deployments become more complex.

The following items are good to consider or have in the future and help set expectations around the current scope and limitations of the library.

1. **Concurrency & Storage Safety**: 
In high-concurrency FastAPI apps, multiple requests may update metrics simultaneously.
SQLite and in-memory backends may require additional locking or batching to avoid race conditions.
For distributed or multi-process deployments, Redis backend is recommended.

2. **Storage Growth & Data Retention**:
Metrics can grow quickly as traffic increases. Long-term retention or exporting large time ranges may lead to slow queries or excessive storage usage. In the future, adding retention policies or automatic cleanup would help limit data size.

3. **Metric Aggregation (Future Optimization)**: Today, metrics are stored at the raw event level. Aggregating older data (e.g., hourly or daily buckets) would reduce storage load and speed up queries. This is especially useful for dashboards or long-term trend analysis.

4. **Multi-Instance / Distributed Deployment Considerations**: In setups with multiple app instances (Gunicorn workers, Kubernetes pods, containers), metrics may fragment across instances when using SQLite or in-memory storage. Redis provides shared storage, but users should be aware of potential consistency nuances.

5. **Query Edge Cases**: Time-series queries may return empty results when no data exists for the given range. Different timezones or clock drift across servers can lead to slight timestamp inconsistencies. Future improvements may include improved bucket alignment and timezone handling.

6. **Error Handling in Metrics Pipeline**: If storage becomes unavailable (disk full, Redis offline), the metric system should fail gracefully. Requests should never break due to metrics collection. Logging or fallback behavior may be added in the future.

7. **Performance Overhead**: Middleware introduces small latency overhead on every request. For extremely high-traffic apps, sampling (recording 1 in N requests) may be useful. A future enhancement may include toggleable "low-overhead" modes.

8. **Metric Labeling & PII Safety**: Users should avoid putting personally identifiable information (PII) into metric labels. Labels are often exported or visualized, so they should remain anonymous and limited in variety.

9. **Background Tasks, Streaming, and WebSockets**: FastAPI supports non-standard request patterns such as: - streaming responses
- WebSockets
- background tasks
HTTP middleware does not capture metrics for these cases by default. Future versions may extend support or provide recommended patterns.

10. **Large Exports & Dashboard Consumption**: The /metrics/export endpoint may become slow if the metric history is large. Pagination, filtering, or pre-aggregated export formats may be considered in future releases.

11. **System Metrics Frequency & Overhead**: If system resource metrics (CPU/memory/disk) are enabled in future versions, sampling frequency will matter. Too frequent polling may add overhead; too infrequent may lose granularity.

12. **Optional Dashboard / UI**: The library currently focuses on collecting and serving metrics, not visualizing them. A minimal built-in dashboard or a plug-and-play UI might be added later to improve usability.
