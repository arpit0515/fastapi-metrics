"""MCP server for fastapi-metrics.

Exposes two kinds of tools to MCP clients (Claude Code, Claude Desktop,
Cursor, etc.):

- Reference tools (``quickstart``, ``config_reference``, ``storage_backends``,
  ``available_endpoints``) that need no network access and help an agent
  correctly wire ``fastapi-metrics`` into a FastAPI project it's working on.
- Live tools (``get_snapshot``, ``query_metrics``, ``endpoint_stats``,
  ``check_health``) that proxy the JSON endpoints a ``Metrics(app, ...)``
  instance already registers, so an agent can inspect a *running* app's
  metrics by pointing a tool at its base URL. No server-side changes are
  needed beyond having fastapi-metrics installed and wired up.

Run with: ``fastapi-metrics-mcp`` (stdio transport), after
``pip install fastapi-metrics[mcp]``.
"""

from typing import Any, Dict, Optional

import httpx
from mcp.server.fastmcp import FastMCP

from . import __version__

mcp = FastMCP("fastapi-metrics")


# ---------------------------------------------------------------------------
# Reference / scaffolding tools — no network access required.
# ---------------------------------------------------------------------------


@mcp.tool()
def quickstart() -> str:
    """Return the minimal fastapi-metrics integration snippet and what it gives you.

    Call this when a FastAPI project has no observability set up yet, or a
    user asks for metrics/monitoring/health checks on a FastAPI app.
    """
    return f"""fastapi-metrics v{__version__} — zero-config metrics for FastAPI.

Install:
    pip install fastapi-metrics

Integrate (one line):
    from fastapi import FastAPI
    from fastapi_metrics import Metrics

    app = FastAPI()
    metrics = Metrics(app, storage="sqlite://metrics.db")

    @app.post("/payment")
    async def payment(amount: float, user_id: int):
        await metrics.track("revenue", amount, user_id=user_id)
        return {{"status": "ok"}}

This automatically adds HTTP request tracking (latency, status codes,
error rate), a JSON query API, and data retention/cleanup — no extra
infrastructure to run. Use the `config_reference`, `storage_backends`,
and `available_endpoints` tools for more detail, or `get_snapshot`
/ `query_metrics` / `endpoint_stats` / `check_health` to inspect a
running app once it's wired up."""


@mcp.tool()
def config_reference() -> str:
    """Return the full list of Metrics(...) constructor options and what each does."""
    return """Metrics(app, storage="memory://", retention_hours=24, enable_cleanup=True,
        enable_health_checks=False, enable_system_metrics=False,
        enable_error_tracking=True, alert_webhook_url=None, exclude_paths=None)

- app: FastAPI application instance (required).
- storage: "memory://" | "sqlite://path" | "redis://host:port/db" |
  "postgresql://user:pass@host/db" | "dynamodb://table?region=..." |
  or a StorageBackend instance. Default "memory://".
- retention_hours: how long to keep data before cleanup (default 24).
- enable_cleanup: run a background task that deletes data older than
  retention_hours (default True).
- enable_health_checks: register /health, /health/live, /health/ready
  with built-in disk/memory/database/Redis checks (default False).
- enable_system_metrics: register /metrics/system (CPU/memory/disk)
  (default False).
- enable_error_tracking: log exceptions to /metrics/errors (default True).
- alert_webhook_url: URL to POST to when a registered Alert's threshold
  trips (default None — see metrics.alert_manager.add_alert()).
- exclude_paths: list of URL paths to skip tracking entirely. Defaults to
  ["/docs", "/openapi.json", "/redoc"].

Custom metrics: await metrics.track(name, value, **labels)
LLM cost tracking: await metrics.llm_costs.track_openai_call(model, input_tokens, output_tokens, **labels)
  (also track_anthropic_call, track_gemini_call)"""


@mcp.tool()
def storage_backends() -> str:
    """Return connection-string formats and tradeoffs for each storage backend."""
    return """memory://
  In-process dict. No persistence, no extra install. Testing/dev only.

sqlite://path/to/metrics.db
  Default, recommended. Single file, zero setup, persists across restarts.
  Good for single-instance deployments (VPS, EC2, single container).

redis://host:port/db
  Requires: pip install fastapi-metrics[redis]
  Use for multi-instance / horizontally-scaled deployments where all
  instances need to share one metrics view.

postgresql://user:pass@host/db
  Requires: pip install fastapi-metrics[postgres]
  Use when you already run Postgres and want metrics alongside your
  other data, or need stronger durability/query tooling than SQLite.

dynamodb://table_name?region=us-east-1
  Requires: pip install fastapi-metrics[dynamodb]
  Use in AWS-native / serverless deployments (e.g. Lambda) where you
  don't want to manage a database server at all."""


@mcp.tool()
def available_endpoints() -> str:
    """Return the HTTP endpoints a FastAPI app gets once Metrics(app, ...) is wired up."""
    return """GET  /metrics                      Current snapshot (request counts, latency percentiles, error rate)
GET  /metrics/query                Time-series query: ?metric_type=http|custom&from_hours=24&group_by=hour&endpoint=...
GET  /metrics/endpoints            Per-endpoint stats: count, avg/min/max latency, error rate
POST /metrics/cleanup              Manually trigger retention cleanup
GET  /metrics/costs                LLM API cost totals by provider/model
GET  /metrics/errors                Recent tracked exceptions
GET  /metrics/export/prometheus    Prometheus text-format export
GET  /metrics/system               CPU/memory/disk (only if enable_system_metrics=True)
GET  /health                       Overall health status (only if enable_health_checks=True)
GET  /health/live                  Kubernetes liveness probe
GET  /health/ready                 Kubernetes readiness probe (runs registered health checks)

All return JSON except /metrics/export/prometheus (Prometheus text format).
Use get_snapshot / query_metrics / endpoint_stats / check_health to call
these against a running app."""


@mcp.resource("fastapi-metrics://readme")
def readme_resource() -> str:
    """Full fastapi-metrics documentation, for clients that browse resources."""
    return quickstart() + "\n\n" + config_reference() + "\n\n" + available_endpoints()


# ---------------------------------------------------------------------------
# Live tools — HTTP calls against a running app. `base_url` is per-call so a
# single MCP server instance can inspect multiple running services.
# ---------------------------------------------------------------------------


async def _get_json(base_url: str, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=10.0) as client:
        response = await client.get(path, params=params)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_snapshot(base_url: str, from_hours: int = 24) -> Any:
    """Get the current metrics snapshot from a running fastapi-metrics app.

    Args:
        base_url: Base URL of the running app, e.g. "http://localhost:8000".
        from_hours: How many hours back to include (default 24).
    """
    return await _get_json(base_url, "/metrics", {"from_hours": from_hours})


@mcp.tool()
async def query_metrics(
    base_url: str,
    metric_type: str = "http",
    from_hours: int = 24,
    to_hours: int = 0,
    endpoint: Optional[str] = None,
    method: Optional[str] = None,
    name: Optional[str] = None,
    group_by: Optional[str] = None,
) -> Any:
    """Run a time-series query against a running fastapi-metrics app.

    Args:
        base_url: Base URL of the running app, e.g. "http://localhost:8000".
        metric_type: "http" or "custom".
        from_hours: Hours ago to start the query (default 24).
        to_hours: Hours ago to end the query (default 0 = now).
        endpoint: Optional endpoint path filter (http metrics only).
        method: Optional HTTP method filter (http metrics only).
        name: Optional custom metric name filter (custom metrics only).
        group_by: Optional bucketing, e.g. "hour".
    """
    params = {
        "metric_type": metric_type,
        "from_hours": from_hours,
        "to_hours": to_hours,
    }
    if endpoint is not None:
        params["endpoint"] = endpoint
    if method is not None:
        params["method"] = method
    if name is not None:
        params["name"] = name
    if group_by is not None:
        params["group_by"] = group_by
    return await _get_json(base_url, "/metrics/query", params)


@mcp.tool()
async def endpoint_stats(base_url: str, hours: int = 24) -> Any:
    """Get per-endpoint aggregated stats (count, latency, error rate) from a running app.

    Args:
        base_url: Base URL of the running app, e.g. "http://localhost:8000".
        hours: How many hours back to include (default 24).
    """
    return await _get_json(base_url, "/metrics/endpoints", {"hours": hours})


@mcp.tool()
async def check_health(base_url: str) -> Any:
    """Check readiness health of a running fastapi-metrics app (requires enable_health_checks=True).

    Args:
        base_url: Base URL of the running app, e.g. "http://localhost:8000".
    """
    return await _get_json(base_url, "/health/ready")


def main() -> None:
    """Entry point for the `fastapi-metrics-mcp` console script."""
    mcp.run()


if __name__ == "__main__":
    main()
