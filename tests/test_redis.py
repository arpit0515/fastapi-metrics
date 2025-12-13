"""
Docstring for tests.test_redis
"""

import asyncio
import datetime
import pytest
from fastapi_metrics.storage.redis import RedisStorage

pytest.importorskip("redis")


@pytest.fixture
async def redis_store():
    """Redis storage fixture - requires Redis to be running."""
    storage = RedisStorage("redis://localhost:6379/0")  # Use DB 15 for tests
    try:
        await storage.initialize()
        # Flush the test database before each test
        await storage.client.flushdb()
        yield storage
    except Exception as e:  # pylint: disable=W0718
        pytest.skip(f"Redis not available: {e}")
    finally:
        # Cleanup
        if storage.client:
            await storage.client.flushdb()
            await storage.close()


@pytest.mark.asyncio
async def test_redis_store_and_query_http_metrics(redis_store):
    """Test Redis HTTP metrics storage."""
    now = datetime.datetime.now(datetime.timezone.utc)

    await redis_store.store_http_metric(
        timestamp=now,
        endpoint="/api/test",
        method="GET",
        status_code=200,
        latency_ms=45.5,
    )

    await redis_store.store_http_metric(
        timestamp=now - datetime.timedelta(minutes=30),
        endpoint="/api/test",
        method="POST",
        status_code=201,
        latency_ms=120.0,
    )

    # Query all
    results = await redis_store.query_http_metrics(
        from_time=now - datetime.timedelta(hours=1),
        to_time=now + datetime.timedelta(minutes=1),
    )

    assert len(results) == 2


@pytest.mark.asyncio
async def test_redis_store_and_query_custom_metrics(redis_store):
    """Test Redis custom metrics storage."""
    now = datetime.datetime.now(datetime.timezone.utc)

    await redis_store.store_custom_metric(
        timestamp=now,
        name="revenue",
        value=99.99,
        labels={"user_id": 123, "plan": "pro"},
    )

    await redis_store.store_custom_metric(
        timestamp=now - datetime.timedelta(minutes=15),
        name="signups",
        value=1,
        labels={"source": "organic"},
    )

    # Query by name
    results = await redis_store.query_custom_metrics(
        from_time=now - datetime.timedelta(hours=1),
        to_time=now + datetime.timedelta(minutes=1),
        name="revenue",
    )

    assert len(results) == 1
    assert results[0]["value"] == 99.99


@pytest.mark.asyncio
async def test_redis_endpoint_stats(redis_store):
    """Test Redis endpoint statistics."""
    now = datetime.datetime.now(datetime.timezone.utc)

    # Store multiple requests to the same endpoint
    for i in range(5):
        await redis_store.store_http_metric(
            timestamp=now + datetime.timedelta(seconds=i),  # Different timestamps
            endpoint="/api/test",
            method="GET",
            status_code=200,
            latency_ms=50.0 + i,
        )

    # Store error
    await redis_store.store_http_metric(
        timestamp=now + datetime.timedelta(seconds=10),  # Different timestamp
        endpoint="/api/test",
        method="GET",
        status_code=500,
        latency_ms=100.0,
    )
    await asyncio.sleep(0.1)

    stats = await redis_store.get_endpoint_stats()

    # Should have exactly 1 endpoint
    assert len(stats) == 1, f"Expected 1 endpoint, got {len(stats)}: {stats}"
    test_stats = stats[0]
    assert test_stats["endpoint"] == "/api/test"
    assert test_stats["method"] == "GET"
    assert test_stats["count"] == 6, f"Expected 6 metrics, got {test_stats['count']}"
    assert test_stats["error_rate"] > 0


@pytest.mark.asyncio
async def test_redis_cleanup_old_data(redis_store):
    """Test Redis data cleanup."""
    now = datetime.datetime.now(datetime.timezone.utc)
    old_time = now - datetime.timedelta(hours=48)

    # Store old data
    await redis_store.store_http_metric(
        timestamp=old_time,
        endpoint="/old",
        method="GET",
        status_code=200,
        latency_ms=50.0,
    )

    # Store new data
    await redis_store.store_http_metric(
        timestamp=now,
        endpoint="/new",
        method="GET",
        status_code=200,
        latency_ms=50.0,
    )

    # Cleanup
    deleted = await redis_store.cleanup_old_data(before=now - datetime.timedelta(hours=24))

    assert deleted >= 1

    # Verify only new data remains
    results = await redis_store.query_http_metrics(
        from_time=now - datetime.timedelta(days=3),
        to_time=now + datetime.timedelta(minutes=1),
    )

    # Should only have new endpoint
    assert all(r["endpoint"] == "/new" for r in results)


@pytest.mark.asyncio
async def test_redis_grouped_query(redis_store):
    """Test Redis grouped queries."""
    now = datetime.datetime.now(datetime.timezone.utc)

    # Store metrics across different hours
    for i in range(3):
        await redis_store.store_http_metric(
            timestamp=now - datetime.timedelta(hours=i),
            endpoint="/api/test",
            method="GET",
            status_code=200,
            latency_ms=50.0,
        )

    # Query with grouping
    results = await redis_store.query_http_metrics(
        from_time=now - datetime.timedelta(hours=5),
        to_time=now + datetime.timedelta(minutes=1),
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


if __name__ == "__main__":
    pytest.main([__file__])
