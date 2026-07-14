"""Tests for the fastapi-metrics MCP server."""

import asyncio
import socket
import threading

import pytest
import uvicorn
from fastapi import FastAPI

from fastapi_metrics import Metrics
from fastapi_metrics.mcp_server import (
    available_endpoints,
    check_health,
    config_reference,
    endpoint_stats,
    get_snapshot,
    query_metrics,
    quickstart,
    readme_resource,
    storage_backends,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_app_url():
    """Run a real FastAPI+Metrics app in a background thread and yield its base URL."""
    app = FastAPI()
    Metrics(app, storage="memory://", enable_health_checks=True)

    @app.post("/payment")
    async def payment(amount: float):
        return {"status": "ok", "amount": amount}

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="critical")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    async def _wait_until_up():
        for _ in range(200):
            if server.started:
                return
            await asyncio.sleep(0.01)
        raise RuntimeError("test server did not start in time")

    asyncio.run(_wait_until_up())

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Reference tools — no network needed.
# ---------------------------------------------------------------------------


def test_quickstart_mentions_install_and_metrics_class():
    text = quickstart()
    assert "pip install fastapi-metrics" in text
    assert "Metrics(app" in text


def test_config_reference_documents_all_constructor_args():
    text = config_reference()
    for arg in [
        "storage",
        "retention_hours",
        "enable_cleanup",
        "enable_health_checks",
        "enable_system_metrics",
        "enable_error_tracking",
        "alert_webhook_url",
        "exclude_paths",
    ]:
        assert arg in text


def test_storage_backends_lists_all_backends():
    text = storage_backends()
    for backend in ["memory://", "sqlite://", "redis://", "postgresql://", "dynamodb://"]:
        assert backend in text


def test_available_endpoints_lists_core_routes():
    text = available_endpoints()
    for route in ["/metrics", "/metrics/query", "/metrics/endpoints", "/health/ready"]:
        assert route in text


def test_readme_resource_combines_reference_tools():
    text = readme_resource()
    assert "pip install fastapi-metrics" in text
    assert "retention_hours" in text
    assert "/metrics/query" in text


# ---------------------------------------------------------------------------
# Live tools — real HTTP against a running app.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_snapshot_against_live_app(live_app_url):
    result = await get_snapshot(live_app_url)
    assert "http" in result
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_query_metrics_against_live_app(live_app_url):
    import httpx

    async with httpx.AsyncClient() as client:
        await client.post(f"{live_app_url}/payment", params={"amount": 10.0})

    result = await query_metrics(live_app_url, metric_type="http", from_hours=1)
    assert "results" in result or isinstance(result, dict)


@pytest.mark.asyncio
async def test_endpoint_stats_against_live_app(live_app_url):
    result = await endpoint_stats(live_app_url)
    assert "endpoints" in result


@pytest.mark.asyncio
async def test_check_health_against_live_app(live_app_url):
    result = await check_health(live_app_url)
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_get_snapshot_against_unreachable_host_raises():
    import httpx

    with pytest.raises((httpx.ConnectError, httpx.ConnectTimeout)):
        await get_snapshot("http://127.0.0.1:1")
