"""
Docstring for tests.test_storage
"""

import datetime
import pytest
from fastapi_metrics.storage.memory import MemoryStorage
from fastapi_metrics.storage.sqlite import SQLiteStorage


@pytest.fixture
def memory_storage():
    """Fixture for in-memory storage."""
    return MemoryStorage()


@pytest.fixture
def memory_store(memory_storage):
    """Alias fixture for tests expecting `memory_store` name."""
    return memory_storage


@pytest.fixture
def sqlite_storage(tmp_path):
    """Fixture for SQLite storage."""
    db_path = tmp_path / "test_metrics.db"
    return SQLiteStorage(str(db_path))


@pytest.mark.asyncio
@pytest.mark.parametrize("storage_fixture", ["memory_storage", "sqlite_storage"])
async def test_store_and_query_http_metrics(storage_fixture, request):
    """
    Docstring for test_store_and_query_http_metrics

    :param storage_fixture: Description
    :type storage_fixture: Literal['memory_storage', 'sqlite_storage']
    :param request: Description
    :type request: FixtureRequest
    """
    storage = request.getfixturevalue(storage_fixture)
    await storage.initialize()

    now = datetime.datetime.now(datetime.timezone.utc)

    # Store metrics
    await storage.store_http_metric(
        timestamp=now,
        endpoint="/api/test",
        method="GET",
        status_code=200,
        latency_ms=45.5,
    )

    await storage.store_http_metric(
        timestamp=now - datetime.timedelta(hours=1),
        endpoint="/api/test",
        method="POST",
        status_code=201,
        latency_ms=120.0,
    )

    # Query all
    results = await storage.query_http_metrics(
        from_time=now - datetime.timedelta(hours=2),
        to_time=now + datetime.timedelta(hours=1),
    )

    assert len(results) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("storage_fixture", ["memory_storage", "sqlite_storage"])
async def test_store_and_query_custom_metrics(storage_fixture, request):
    """
    Docstring for test_store_and_query_custom_metrics

    :param storage_fixture: Description
    :type storage_fixture: Literal['memory_storage', 'sqlite_storage']
    :param request: Description
    :type request: FixtureRequest
    """
    storage = request.getfixturevalue(storage_fixture)
    await storage.initialize()

    now = datetime.datetime.now(datetime.timezone.utc)

    # Store metrics
    await storage.store_custom_metric(
        timestamp=now,
        name="revenue",
        value=99.99,
        labels={"user_id": 123, "plan": "pro"},
    )

    await storage.store_custom_metric(
        timestamp=now - datetime.timedelta(minutes=30),
        name="signups",
        value=1,
        labels={"source": "organic"},
    )

    # Query by name
    results = await storage.query_custom_metrics(
        from_time=now - datetime.timedelta(hours=1),
        to_time=now + datetime.timedelta(hours=1),
        name="revenue",
    )

    assert len(results) == 1
    assert results[0]["value"] == 99.99


@pytest.mark.asyncio
@pytest.mark.parametrize("storage_fixture", ["memory_storage", "sqlite_storage"])
async def test_endpoint_stats(storage_fixture, request):
    """
    Docstring for test_endpoint_stats

    :param storage_fixture: Description
    :type storage_fixture: Literal['memory_storage', 'sqlite_storage']
    :param request: Description
    :type request: FixtureRequest
    """
    storage = request.getfixturevalue(storage_fixture)
    await storage.initialize()

    now = datetime.datetime.now(datetime.timezone.utc)

    # Store multiple requests
    for i in range(5):
        await storage.store_http_metric(
            timestamp=now,
            endpoint="/api/test",
            method="GET",
            status_code=200,
            latency_ms=50.0 + i,
        )

    # Store error
    await storage.store_http_metric(
        timestamp=now,
        endpoint="/api/test",
        method="GET",
        status_code=500,
        latency_ms=100.0,
    )

    stats = await storage.get_endpoint_stats()

    assert len(stats) == 1
    assert stats[0]["endpoint"] == "/api/test"
    assert stats[0]["count"] == 6
    assert stats[0]["error_rate"] > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("storage_fixture", ["memory_storage", "sqlite_storage"])
async def test_cleanup_old_data(storage_fixture, request):
    """
    Docstring for test_cleanup_old_data

    :param storage_fixture: Description
    :type storage_fixture: Literal['memory_storage', 'sqlite_storage']
    :param request: Description
    :type request: FixtureRequest
    """
    storage = request.getfixturevalue(storage_fixture)
    await storage.initialize()

    now = datetime.datetime.now(datetime.timezone.utc)
    old_time = now - datetime.timedelta(hours=48)

    # Store old and new data
    await storage.store_http_metric(
        timestamp=old_time,
        endpoint="/old",
        method="GET",
        status_code=200,
        latency_ms=50.0,
    )

    await storage.store_http_metric(
        timestamp=now,
        endpoint="/new",
        method="GET",
        status_code=200,
        latency_ms=50.0,
    )

    # Cleanup data older than 24 hours
    deleted = await storage.cleanup_old_data(before=now - datetime.timedelta(hours=24))

    assert deleted == 1

    # Verify only new data remains
    results = await storage.query_http_metrics(
        from_time=now - datetime.timedelta(days=3),
        to_time=now + datetime.timedelta(hours=1),
    )

    assert len(results) == 1
    assert results[0]["endpoint"] == "/new"


@pytest.mark.asyncio
async def test_grouped_query(memory_store):
    """
    Docstring for test_grouped_query

    :param memory_store: Description
    :type memory_store: MemoryStorage
    """
    await memory_store.initialize()
    now = datetime.datetime.now(datetime.timezone.utc)

    # Store metrics across different hours
    for i in range(3):
        await memory_store.store_http_metric(
            timestamp=now - datetime.timedelta(hours=i),
            endpoint="/api/test",
            method="GET",
            status_code=200,
            latency_ms=50.0,
        )

    # Query with grouping
    results = await memory_store.query_http_metrics(
        from_time=now - datetime.timedelta(hours=5),
        to_time=now + datetime.timedelta(hours=1),
        group_by="hour",
    )

    assert len(results) == 3
    assert "count" in results[0]
    assert "avg_latency_ms" in results[0]


if __name__ == "__main__":
    pytest.main([__file__])
