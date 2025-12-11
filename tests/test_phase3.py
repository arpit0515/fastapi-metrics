"""Tests for Phase 3 features: LLM costs, system metrics, Prometheus export, alerting."""

import datetime
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_metrics import Metrics, Alert
from fastapi_metrics.exporters.prometheus import PrometheusExporter
from fastapi_metrics.alerting import AlertManager
from fastapi_metrics.storage.memory import MemoryStorage


@pytest.fixture
def app_with_phase3():
    """App with Phase 3 features enabled."""
    app = FastAPI()

    metrics = Metrics(
        app,
        storage="memory://",
        enable_system_metrics=True,
        alert_webhook_url="https://example.com/webhook",
    )

    @app.get("/")
    async def root():
        return {"status": "ok"}

    return app, metrics


@pytest.fixture
def client_phase3(app_with_phase3):
    """Test client for app with Phase 3 features."""
    app, _ = app_with_phase3
    return TestClient(app)


# LLM Cost Tracking Tests
def test_llm_cost_tracker_openai():
    """Test OpenAI cost calculation."""
    metrics = Metrics(FastAPI(), storage="memory://")
    tracker = metrics.llm_costs

    # GPT-4o: $2.5/1M input, $10/1M output
    cost = tracker.calculate_openai_cost("gpt-4o", 1000, 2000)
    expected = (1000 / 1_000_000 * 2.5) + (2000 / 1_000_000 * 10)
    assert abs(cost - expected) < 0.0001


def test_llm_cost_tracker_anthropic():
    """Test Anthropic cost calculation."""
    metrics = Metrics(FastAPI(), storage="memory://")
    tracker = metrics.llm_costs

    # Claude 3.5 Sonnet: $3/1M input, $15/1M output
    cost = tracker.calculate_anthropic_cost("claude-3-5-sonnet", 1000, 2000)
    expected = (1000 / 1_000_000 * 3.0) + (2000 / 1_000_000 * 15)
    assert abs(cost - expected) < 0.0001


@pytest.mark.asyncio
async def test_track_openai_call():
    """Test tracking OpenAI API call."""
    storage = MemoryStorage()
    await storage.initialize()

    app = FastAPI()
    metrics = Metrics(app, storage=storage)

    await metrics.llm_costs.track_openai_call(
        model="gpt-4o",
        input_tokens=100,
        output_tokens=200,
        user_id=123,
    )

    # Check metrics were stored
    now = datetime.datetime.now(datetime.timezone.utc)
    costs = await storage.query_custom_metrics(
        from_time=now - datetime.timedelta(minutes=1),
        to_time=now + datetime.timedelta(minutes=1),
        name="llm_cost",
    )

    assert len(costs) == 1
    assert costs[0]["labels"]["provider"] == "openai"


@pytest.mark.asyncio
async def test_track_anthropic_call():
    """Test tracking Anthropic API call."""
    storage = MemoryStorage()
    await storage.initialize()

    app = FastAPI()
    metrics = Metrics(app, storage=storage)

    await metrics.llm_costs.track_anthropic_call(
        model="claude-3-5-sonnet",
        input_tokens=150,
        output_tokens=300,
        endpoint="/chat",
    )

    # Check metrics were stored
    now = datetime.datetime.now(datetime.timezone.utc)
    costs = await storage.query_custom_metrics(
        from_time=now - datetime.timedelta(minutes=1),
        to_time=now + datetime.timedelta(minutes=1),
        name="llm_cost",
    )

    assert len(costs) == 1
    assert costs[0]["labels"]["provider"] == "anthropic"


# System Metrics Tests
def test_system_metrics_collector():
    """Test system metrics collection."""
    app = FastAPI()
    metrics = Metrics(app, storage="memory://", enable_system_metrics=True)
    collector = metrics.system_metrics

    # Test CPU
    cpu = collector.get_cpu_percent()
    assert 0 <= cpu <= 100

    # Test Memory
    mem = collector.get_memory_stats()
    assert "percent" in mem
    assert "available_gb" in mem
    assert 0 <= mem["percent"] <= 100

    # Test Disk
    disk = collector.get_disk_stats()
    assert "percent" in disk
    assert "free_gb" in disk
    assert 0 <= disk["percent"] <= 100


@pytest.mark.asyncio
async def test_system_metrics_tracking():
    """Test system metrics are tracked."""
    storage = MemoryStorage()
    await storage.initialize()

    app = FastAPI()
    metrics = Metrics(app, storage=storage, enable_system_metrics=True)

    await metrics.system_metrics.collect_and_track()

    # Check metrics were stored
    now = datetime.datetime.now(datetime.timezone.utc)
    cpu_metrics = await storage.query_custom_metrics(
        from_time=now - datetime.timedelta(minutes=1),
        to_time=now + datetime.timedelta(minutes=1),
        name="system_cpu_percent",
    )

    assert len(cpu_metrics) >= 1


def test_system_metrics_endpoint(client_phase3):
    """Test /metrics/system endpoint."""
    response = client_phase3.get("/metrics/system")
    assert response.status_code == 200
    data = response.json()

    assert "cpu_percent" in data
    assert "memory" in data
    assert "disk" in data


# Prometheus Export Tests
@pytest.mark.asyncio
async def test_prometheus_exporter():
    """Test Prometheus export format."""
    storage = MemoryStorage()
    await storage.initialize()

    # Add some test data
    now = datetime.datetime.now(datetime.timezone.utc)
    await storage.store_http_metric(
        timestamp=now,
        endpoint="/api/test",
        method="GET",
        status_code=200,
        latency_ms=50.0,
    )

    exporter = PrometheusExporter(storage)
    output = await exporter.export_http_metrics(hours=1)

    assert "http_requests_total" in output
    assert "http_request_duration_ms" in output
    assert "http_error_rate" in output
    assert 'endpoint="/api/test"' in output


def test_prometheus_export_endpoint(client_phase3):
    """Test /metrics/export/prometheus endpoint."""
    response = client_phase3.get("/metrics/export/prometheus")
    assert response.status_code == 200

    # Should be plain text
    assert (
        "text" in response.headers.get("content-type", "").lower()
        or response.headers.get("content-type") == "application/json"
    )


# LLM Costs Endpoint Tests
@pytest.mark.asyncio
async def test_llm_costs_endpoint():
    """Test /metrics/costs endpoint."""
    storage = MemoryStorage()
    await storage.initialize()

    app = FastAPI()
    metrics = Metrics(app, storage=storage)

    # Add some cost data
    await metrics.llm_costs.track_openai_call(
        model="gpt-4o",
        input_tokens=1000,
        output_tokens=2000,
    )

    client = TestClient(app)
    response = client.get("/metrics/costs?hours=1")
    assert response.status_code == 200

    data = response.json()
    assert "total_cost" in data
    assert "by_provider" in data
    assert "openai" in data["by_provider"]


# Alerting Tests
@pytest.mark.asyncio
async def test_alert_creation():
    """Test alert creation."""
    alert = Alert(
        name="high_error_rate",
        metric_name="error_rate",
        threshold=0.05,
        comparison=">",
        window_minutes=5,
    )

    assert alert.name == "high_error_rate"
    assert alert.check(0.1) is True
    assert alert.check(0.01) is False


@pytest.mark.asyncio
async def test_alert_manager():
    """Test alert manager."""
    storage = MemoryStorage()
    await storage.initialize()

    app = FastAPI()
    metrics = Metrics(app, storage=storage)

    manager = AlertManager(metrics)

    # Add alert
    alert = Alert(
        name="test_alert",
        metric_name="test_metric",
        threshold=100,
        comparison=">",
    )
    manager.add_alert(alert)

    assert "test_alert" in manager.alerts

    # Remove alert
    manager.remove_alert("test_alert")
    assert "test_alert" not in manager.alerts


@pytest.mark.asyncio
async def test_alert_checking():
    """Test alert threshold checking."""
    storage = MemoryStorage()
    await storage.initialize()

    app = FastAPI()
    metrics = Metrics(app, storage=storage)

    # Track a metric
    await metrics.track("test_metric", 150)

    manager = AlertManager(metrics)
    alert = Alert(
        name="test_alert",
        metric_name="test_metric",
        threshold=100,
        comparison=">",
        window_minutes=5,
    )
    manager.add_alert(alert)

    # Check alerts
    await manager.check_alerts()

    # Alert should have triggered
    assert alert.last_triggered is not None


def test_phase3_app_initialization(app_with_phase3):
    """Test app initializes with Phase 3 features."""
    _, metrics = app_with_phase3

    assert metrics.llm_costs is not None
    assert metrics.system_metrics is not None
    assert metrics.alert_manager is not None


def test_phase3_endpoints_exist(client_phase3):
    """Test all Phase 3 endpoints are registered."""
    # System metrics
    response = client_phase3.get("/metrics/system")
    assert response.status_code == 200

    # Costs
    response = client_phase3.get("/metrics/costs")
    assert response.status_code == 200

    # Prometheus export
    response = client_phase3.get("/metrics/export/prometheus")
    assert response.status_code == 200
