import pytest
from datetime import datetime, timedelta

# Skip all tests if redis is not installed
pytest.importorskip("redis")

from fastapi_metrics.storage.redis import RedisStorage


@pytest.fixture
async def redis_storage():
    """Redis storage fixture - requires Redis to be running."""
    storage = RedisStorage("redis://localhost:6379/15")  # Use DB 15 for tests
    try:
        await storage.initialize()
        # Flush the test database before each test
        await storage.client.flushdb()
        yield storage
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")
    finally:
        # Cleanup
        if storage.client:
            await storage.client.flushdb()
            await storage.close()


@pytest.mark.asyncio
async def test_redis_store_and_query_http_metrics(redis_storage):
    """Test Redis HTTP metrics storage."""
    now = datetime.utcnow()
    
    await redis_storage.store_http_metric(
        timestamp=now,
        endpoint="/api/test",
        method="GET",
        status_code=200,
        latency_ms=45.5,
    )
    
    await redis_storage.store_http_metric(
        timestamp=now - timedelta(minutes=30),
        endpoint="/api/test",
        method="POST",
        status_code=201,
        latency_ms=120.0,
    )
    
    # Query all
    results = await redis_storage.query_http_metrics(
        from_time=now - timedelta(hours=1),
        to_time=now + timedelta(minutes=1),
    )
    
    assert len(results) == 2


@pytest.mark.asyncio
async def test_redis_store_and_query_custom_metrics(redis_storage):
    """Test Redis custom metrics storage."""
    now = datetime.utcnow()
    
    await redis_storage.store_custom_metric(
        timestamp=now,
        name="revenue",
        value=99.99,
        labels={"user_id": 123, "plan": "pro"},
    )
    
    await redis_storage.store_custom_metric(
        timestamp=now - timedelta(minutes=15),
        name="signups",
        value=1,
        labels={"source": "organic"},
    )
    
    # Query by name
    results = await redis_storage.query_custom_metrics(
        from_time=now - timedelta(hours=1),
        to_time=now + timedelta(minutes=1),
        name="revenue",
    )
    
    assert len(results) == 1
    assert results[0]["value"] == 99.99


@pytest.mark.asyncio
async def test_redis_endpoint_stats(redis_storage):
    """Test Redis endpoint statistics."""
    now = datetime.utcnow()
    
    # Store multiple requests to the same endpoint
    for i in range(5):
        await redis_storage.store_http_metric(
            timestamp=now + timedelta(seconds=i),  # Different timestamps
            endpoint="/api/test",
            method="GET",
            status_code=200,
            latency_ms=50.0 + i,
        )
    
    # Store error
    await redis_storage.store_http_metric(
        timestamp=now + timedelta(seconds=10),  # Different timestamp
        endpoint="/api/test",
        method="GET",
        status_code=500,
        latency_ms=100.0,
    )
    
    # Give Redis a moment to process
    import asyncio
    await asyncio.sleep(0.1)
    
    stats = await redis_storage.get_endpoint_stats()
    
    # Should have exactly 1 endpoint
    assert len(stats) == 1, f"Expected 1 endpoint, got {len(stats)}: {stats}"
    test_stats = stats[0]
    assert test_stats["endpoint"] == "/api/test"
    assert test_stats["method"] == "GET"
    assert test_stats["count"] == 6, f"Expected 6 metrics, got {test_stats['count']}"
    assert test_stats["error_rate"] > 0


@pytest.mark.asyncio
async def test_redis_cleanup_old_data(redis_storage):
    """Test Redis data cleanup."""
    now = datetime.utcnow()
    old_time = now - timedelta(hours=48)
    
    # Store old data
    await redis_storage.store_http_metric(
        timestamp=old_time,
        endpoint="/old",
        method="GET",
        status_code=200,
        latency_ms=50.0,
    )
    
    # Store new data
    await redis_storage.store_http_metric(
        timestamp=now,
        endpoint="/new",
        method="GET",
        status_code=200,
        latency_ms=50.0,
    )
    
    # Cleanup
    deleted = await redis_storage.cleanup_old_data(before=now - timedelta(hours=24))
    
    assert deleted >= 1
    
    # Verify only new data remains
    results = await redis_storage.query_http_metrics(
        from_time=now - timedelta(days=3),
        to_time=now + timedelta(minutes=1),
    )
    
    # Should only have new endpoint
    assert all(r["endpoint"] == "/new" for r in results)


@pytest.mark.asyncio
async def test_redis_grouped_query(redis_storage):
    """Test Redis grouped queries."""
    now = datetime.utcnow()
    
    # Store metrics across different hours
    for i in range(3):
        await redis_storage.store_http_metric(
            timestamp=now - timedelta(hours=i),
            endpoint="/api/test",
            method="GET",
            status_code=200,
            latency_ms=50.0,
        )
    
    # Query with grouping
    results = await redis_storage.query_http_metrics(
        from_time=now - timedelta(hours=5),
        to_time=now + timedelta(minutes=1),
        group_by="hour",
    )
    
    assert len(results) >= 3
    assert "count" in results[0]
    assert "avg_latency_ms" in results[0]


@pytest.mark.asyncio
async def test_redis_connection_error():
    """Test Redis connection error handling."""
    storage = RedisStorage("redis://invalid-host:9999/0")
    
    with pytest.raises(Exception):
        await storage.initialize()
