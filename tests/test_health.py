"""
Docstring for tests.test_health
"""

import pytest
from fastapi_metrics.health.checks import (
    DiskSpaceCheck,
    MemoryCheck,
    DatabaseCheck,
)
from fastapi_metrics.health.endpoints import HealthManager
from fastapi_metrics.storage.memory import MemoryStorage


@pytest.mark.asyncio
async def test_disk_space_check():
    """Test disk space health check."""
    check = DiskSpaceCheck(path="/", min_free_gb=0.1)
    result = await check.check()

    assert "status" in result
    assert result["status"] in ["ok", "error"]
    if result["status"] == "ok":
        assert "free_gb" in result
        assert "percent_used" in result


@pytest.mark.asyncio
async def test_memory_check():
    """Test memory health check."""
    check = MemoryCheck(max_percent=95.0)
    result = await check.check()

    assert "status" in result
    assert result["status"] in ["ok", "error"]
    assert "percent_used" in result
    assert "available_gb" in result


@pytest.mark.asyncio
async def test_database_check():
    """Test database connectivity check."""
    storage = MemoryStorage()
    await storage.initialize()

    check = DatabaseCheck(storage)
    result = await check.check()

    assert "status" in result
    assert result["status"] == "ok"
    assert "message" in result


@pytest.mark.asyncio
async def test_database_check_failure():
    """Test database check with failed connection."""

    # Create a mock storage that will fail
    class FailingStorage:
        """
        Docstring for FailingStorage
        """

        async def query_http_metrics(self, from_time, to_time):
            """
            Docstring for query_http_metrics

            :param self: Description
            :param from_time: Description
            :param to_time: Description
            """
            raise Exception("Database connection failed")  # pylint: disable=W0719

    storage = FailingStorage()
    check = DatabaseCheck(storage)
    result = await check.check()

    assert result["status"] == "error"
    assert "message" in result


@pytest.mark.asyncio
async def test_health_manager():
    """Test health manager with multiple checks."""
    manager = HealthManager()

    # Add checks
    manager.add_check("disk", DiskSpaceCheck(min_free_gb=0.1))
    manager.add_check("memory", MemoryCheck(max_percent=95.0))

    # Run checks
    result = await manager.run_checks()

    assert "status" in result
    assert "checks" in result
    assert "disk" in result["checks"]
    assert "memory" in result["checks"]


@pytest.mark.asyncio
async def test_health_manager_liveness():
    """Test liveness probe."""
    manager = HealthManager()
    result = await manager.liveness()

    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_health_manager_readiness():
    """Test readiness probe."""
    manager = HealthManager()

    storage = MemoryStorage()
    await storage.initialize()

    manager.add_check("database", DatabaseCheck(storage))

    result = await manager.readiness()

    assert "status" in result
    assert "checks" in result


@pytest.mark.asyncio
async def test_health_manager_readiness_failure():
    """Test readiness probe with failing check."""
    manager = HealthManager()

    # Add a check that will fail
    class FailingStorage:
        """
        Docstring for FailingStorage
        """

        async def query_http_metrics(self, from_time, to_time):
            """
            Docstring for query_http_metrics

            :param self: Description
            :param from_time: Description
            :param to_time: Description
            """
            raise Exception("Connection failed")  # pylint: disable=W0719

    storage = FailingStorage()
    manager.add_check("database", DatabaseCheck(storage))

    result = await manager.readiness()

    assert result["status"] == "error"
    assert result["checks"]["database"]["status"] == "error"
