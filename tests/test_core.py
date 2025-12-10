import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_metrics import Metrics


@pytest.fixture
def app():
    app = FastAPI()

    metrics = Metrics(app, storage="memory://", retention_hours=24)

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.post("/payment")
    async def payment(amount: float, user_id: int):
        await metrics.track("revenue", amount, user_id=user_id)
        return {"status": "success"}

    return app


@pytest.fixture
def client(app):
    return TestClient(app)


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
    # Track custom metrics
    response = client.post("/payment?amount=99.99&user_id=123")
    assert response.status_code == 200

    # Query custom metrics
    response = client.get("/metrics/query?metric_type=custom&name=revenue&from_hours=1")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    assert data["results"][0]["name"] == "revenue"
    assert data["results"][0]["value"] == 99.99


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
    app = FastAPI()
    db_path = tmp_path / "test_metrics.db"
    metrics = Metrics(app, storage=f"sqlite://{db_path}")

    # Use context manager to trigger startup/shutdown events
    with TestClient(app) as client:

        @app.get("/")
        async def root():
            return {"message": "test"}

        # Make request
        response = client.get("/")
        assert response.status_code == 200

        # Check metrics are stored
        response = client.get("/metrics/query?metric_type=http&from_hours=1")
        assert response.status_code == 200


def test_invalid_storage_backend():
    """Test invalid storage backend raises error."""
    app = FastAPI()

    with pytest.raises(ValueError, match="Unknown storage backend"):
        Metrics(app, storage="invalid://backend")
