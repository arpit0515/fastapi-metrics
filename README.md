# FastAPI Metrics

[![PyPI version](https://img.shields.io/pypi/v/fastapi-metrics.svg)](https://pypi.org/project/fastapi-metrics/)
[![CI](https://github.com/arpit0515/fastapi-metrics/actions/workflows/ci.yml/badge.svg)](https://github.com/arpit0515/fastapi-metrics/actions/workflows/ci.yml)
[![Python versions](https://img.shields.io/pypi/pyversions/fastapi-metrics.svg)](https://pypi.org/project/fastapi-metrics/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Zero-config metrics and observability for FastAPI apps.** No Prometheus. No Grafana. No containers required — just one line of code.

```bash
pip install fastapi-metrics
```

```python
from fastapi import FastAPI
from fastapi_metrics import Metrics

app = FastAPI()
metrics = Metrics(app, storage="sqlite://metrics.db")

@app.post("/payment")
async def payment(amount: float, user_id: int):
    await metrics.track("revenue", amount, user_id=user_id)
    return {"status": "ok"}
```

That's it. Your app now has HTTP request tracking, a JSON query API, and automatic data retention — no infrastructure to run.

## What's included

- **HTTP metrics** — latency (p50/p95/p99), status codes, error rate, active requests, per-endpoint stats — collected automatically for every request.
- **Custom business metrics** — `await metrics.track("revenue", 99.99, plan="pro")` for anything you care about (signups, revenue, feature usage).
- **Storage backends** — in-memory, SQLite (default, zero setup), Redis, PostgreSQL, and DynamoDB, so you can start local and grow into a multi-instance deployment without changing your code.
- **Kubernetes-ready health checks** — `/health`, `/health/live`, `/health/ready`, with built-in disk/memory/database/Redis checks.
- **LLM cost tracking** — auto-priced token accounting for OpenAI, Anthropic, and Gemini calls.
- **Threshold-based alerting** — webhook notifications when a metric crosses a threshold.
- **Prometheus export** — `/metrics/export/prometheus` if you outgrow the JSON API and want to feed a real Prometheus/Grafana stack.
- **AI-agent friendly** — ships an MCP server so coding agents (Claude Code, Cursor, etc.) know this library exists and can query a running app's metrics directly. See [Use with AI coding agents](#use-with-ai-coding-agents-mcp) below.

## Storage options

```python
Metrics(app, storage="memory://")                 # testing/dev, nothing persisted
Metrics(app, storage="sqlite://metrics.db")        # recommended default, single file
Metrics(app, storage="redis://localhost:6379/0")   # multi-instance / distributed deployments
Metrics(app, storage="postgresql://user:pass@host/db")
Metrics(app, storage="dynamodb://table_name?region=us-east-1")
```

Redis/Postgres/DynamoDB need their client library installed — install with the matching extra:

```bash
pip install fastapi-metrics[redis]
pip install fastapi-metrics[postgres]
pip install fastapi-metrics[dynamodb]
pip install fastapi-metrics[all]       # everything
```

## Configuration

```python
metrics = Metrics(
    app,
    storage="sqlite://metrics.db",
    retention_hours=24,               # how long to keep data
    enable_cleanup=True,              # auto-delete data older than retention_hours
    enable_health_checks=False,       # registers /health, /health/live, /health/ready
    enable_system_metrics=False,      # registers /metrics/system (CPU/memory/disk)
    enable_error_tracking=True,       # log exceptions to /metrics/errors
    alert_webhook_url=None,           # webhook to POST to when an alert threshold trips
    exclude_paths=None,               # paths to skip tracking; defaults to ["/docs", "/openapi.json", "/redoc"]
)
```

## Built-in API endpoints

Once `Metrics(app, ...)` is wired up, your app automatically exposes:

| Endpoint | Description |
|---|---|
| `GET /metrics` | Current snapshot (request counts, latency percentiles, error rate) |
| `GET /metrics/query` | Time-series queries — `?metric_type=http\|custom&from_hours=24&group_by=hour&endpoint=...` |
| `GET /metrics/endpoints` | Per-endpoint aggregated stats (count, avg/min/max latency, error rate) |
| `POST /metrics/cleanup` | Manually trigger retention cleanup |
| `GET /metrics/costs` | LLM API cost totals, broken down by provider/model |
| `GET /metrics/errors` | Recent tracked exceptions |
| `GET /metrics/export/prometheus` | Prometheus text-format export |
| `GET /metrics/system` | CPU/memory/disk (if `enable_system_metrics=True`) |
| `GET /health`, `/health/live`, `/health/ready` | Kubernetes probes (if `enable_health_checks=True`) |

These return plain JSON, so tools like Retool, Bubble, or a hand-rolled dashboard can consume them directly:

```javascript
fetch('/metrics/query?metric_type=custom&name=revenue&group_by=hour&from_hours=24')
  .then(r => r.json())
  .then(data => renderChart(data.results));
```

## Tracking custom metrics

```python
await metrics.track("revenue", 99.99, user_id=123, plan="pro")
await metrics.track("signups", 1, source="organic")
await metrics.track("api_calls", 1, endpoint="/search")
```

## LLM cost tracking

```python
await metrics.llm_costs.track_openai_call("gpt-4o", input_tokens=512, output_tokens=128, endpoint="/chat")
await metrics.llm_costs.track_anthropic_call("claude-sonnet-4", input_tokens=800, output_tokens=200)
await metrics.llm_costs.track_gemini_call("gemini-2.0-flash", input_tokens=300, output_tokens=90)
```

Then query `GET /metrics/costs` for totals by provider and model. Pricing tables live in `fastapi_metrics/collectors/llm_costs.py` — update them there if pricing changes.

## Alerting

```python
from fastapi_metrics import Alert

metrics = Metrics(app, storage="sqlite://metrics.db", alert_webhook_url="https://hooks.example.com/alert")
metrics.alert_manager.add_alert(
    Alert(name="high_error_rate", metric_name="error_rate", metric_type="http", threshold=0.05, comparison=">")
)
```

## CLI tools

```bash
pip install fastapi-metrics[cli]
fastapi-metrics-setup   # interactive setup wizard
fastapi-metrics         # query metrics from the command line
```

## Use with AI coding agents (MCP)

```bash
pip install fastapi-metrics[mcp]
```

Add to your MCP client config (e.g. Claude Code's `.mcp.json`, Claude Desktop's config, or Cursor's MCP settings):

```json
{
  "mcpServers": {
    "fastapi-metrics": {
      "command": "fastapi-metrics-mcp"
    }
  }
}
```

This gives the agent:

- **Reference tools** (no network needed) — `quickstart`, `config_reference`, `storage_backends`, `available_endpoints` — so it knows this library exists and wires it up correctly instead of reaching for something heavier.
- **Live tools** — `get_snapshot`, `query_metrics`, `endpoint_stats`, `check_health` — each takes a `base_url` and calls the JSON endpoints above against a *running* app, so the agent can answer "why did latency spike" or "is this deploy healthy" during a coding session without you copy-pasting curl output.

## Requirements

- Python 3.8+
- FastAPI 0.100.0+

## Development

```bash
git clone https://github.com/arpit0515/fastapi-metrics
cd fastapi-metrics
pip install -e ".[dev]"
pytest
```

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the project's internal design notes and future plans, and [`CHANGELOG.md`](CHANGELOG.md) for release history.

## Not designed for

- Distributed tracing or log aggregation
- APM-level profiling
- Replacing Prometheus/Grafana at large scale (though the Prometheus export endpoint lets you bridge into that world when you outgrow this)

## Contributing

Contributions welcome — this is an early-stage project focused on staying simple. Open an issue or PR at [github.com/arpit0515/fastapi-metrics](https://github.com/arpit0515/fastapi-metrics).

## License

MIT — see [LICENSE](LICENSE).
