"""
Docstring for tests.test_core
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_metrics import Metrics


@pytest.fixture
def app():
    """Main app fixture."""
    in_app = FastAPI()

    metrics = Metrics(in_app, storage="memory://", retention_hours=24)

    @in_app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @in_app.post("/payment")
    async def payment(amount: float, user_id: int):
        await metrics.track("revenue", amount, user_id=user_id)
        return {"status": "success"}

    return in_app


@pytest.fixture
def app_with_health():
    """App with health checks enabled."""
    in_app = FastAPI()

    Metrics(in_app, storage="memory://", retention_hours=24, enable_health_checks=True)

    @in_app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    return in_app


@pytest.fixture
def client(app):
    """Test client for the main app."""
    return TestClient(app)


@pytest.fixture
def health_client(app_with_health):
    """Test client for app with health checks."""
    return TestClient(app_with_health)


def test_metrics_endpoint(client):
    """Test /metrics endpoint exists and returns data."""
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "active_requests" in data
    assert "timestamp" in data


def test_http_tracking(client):
    """Test HTTP requests are tracked automatically."""
    # Make some requests
    client.get("/test")
    client.get("/test")

    # Query metrics
    response = client.get("/metrics/query?metric_type=http&from_hours=1")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 2


def test_custom_metrics_tracking(client):
    """Test custom business metrics are tracked."""
    # Track custom metric
    response = client.post("/payment?amount=50.0&user_id=1")
    assert response.status_code == 200

    # Query custom metrics
    response = client.get("/metrics/query?metric_type=custom&name=revenue&from_hours=1")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    assert data["results"][0]["name"] == "revenue"
    assert data["results"][0]["value"] == 50.0


def test_endpoint_stats(client):
    """Test per-endpoint statistics."""
    # Make requests
    client.get("/test")
    client.post("/payment?amount=50.0&user_id=1")

    # Get stats
    response = client.get("/metrics/endpoints")
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data
    assert len(data["endpoints"]) > 0


def test_query_with_filters(client):
    """Test querying with various filters."""
    # Make requests
    client.get("/test")

    # Query with endpoint filter
    response = client.get("/metrics/query?metric_type=http&endpoint=/test&from_hours=1")
    assert response.status_code == 200
    data = response.json()

    # All results should be for /test endpoint
    for result in data["results"]:
        if isinstance(result, dict) and "endpoint" in result:
            assert result["endpoint"] == "/test"


def test_grouped_query(client):
    """Test grouping metrics by hour."""
    # Make requests
    client.get("/test")
    client.get("/test")

    # Query with grouping
    response = client.get("/metrics/query?metric_type=http&group_by=hour&from_hours=1")
    assert response.status_code == 200
    data = response.json()

    # Results should be grouped
    if data["count"] > 0:
        assert "count" in data["results"][0]


def test_cleanup_endpoint(client):
    """Test manual cleanup endpoint."""
    # Make some requests first
    client.get("/test")

    # Trigger cleanup
    response = client.post("/metrics/cleanup?hours_to_keep=0")
    assert response.status_code == 200
    data = response.json()
    assert "deleted_records" in data
    assert "cleaned_before" in data


def test_sqlite_storage(tmp_path):
    """Test SQLite storage initialization."""
    in_app = FastAPI()
    db_path = tmp_path / "test_metrics.db"
    Metrics(in_app, storage=f"sqlite://{db_path}")

    # Use context manager to trigger startup/shutdown events
    with TestClient(in_app) as in_client:

        @in_app.get("/")
        async def root():
            return {"message": "test"}

        # Make request
        response = in_client.get("/")
        assert response.status_code == 200

        # Check metrics are stored
        response = in_client.get("/metrics/query?metric_type=http&from_hours=1")
        assert response.status_code == 200


def test_invalid_storage_backend():
    """Test invalid storage backend raises error."""
    in_app = FastAPI()

    with pytest.raises(ValueError, match="Unknown storage backend"):
        Metrics(in_app, storage="invalid://backend")


def test_health_endpoints(health_client):
    """Test health check endpoints are registered when enabled."""
    # Test /health
    response = health_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data

    # Test /health/live
    response = health_client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

    # Test /health/ready
    response = health_client.get("/health/ready")
    assert response.status_code in [200, 503]  # May be 503 if checks fail
    data = response.json()
    assert "status" in data


def test_health_not_enabled(client):
    """Test health endpoints don't exist when not enabled."""
    response = client.get("/health")
    assert response.status_code == 404

    response = client.get("/health/live")
    assert response.status_code == 404

    response = client.get("/health/ready")
    assert response.status_code == 404


@pytest.mark.skipif(
    not pytest.importorskip("redis", reason="Redis not installed"),
    reason="Redis package not available",
)
def test_redis_storage_initialization():
    """Test Redis storage can be initialized (requires Redis running)."""
    in_app = FastAPI()

    try:
        Metrics(in_app, storage="redis://localhost:6379/15")

        with TestClient(in_app) as in_client:

            @in_app.get("/")
            async def root():
                return {"message": "test"}

            response = in_client.get("/")
            assert response.status_code == 200

            # Check metrics endpoint
            response = in_client.get("/metrics")
            assert response.status_code == 200
    except Exception as e:  # pylint: disable=W0718
        pytest.skip(f"Redis not available: {e}")


if __name__ == __name__ == "__main__":
    pytest.main([__file__])
