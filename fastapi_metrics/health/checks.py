"""Health check implementations for system resources and databases."""

import datetime
from abc import ABC, abstractmethod
from typing import Dict, Any
import psutil


class HealthCheck(ABC):
    """Base class for health checks."""

    @abstractmethod
    async def check(self) -> Dict[str, Any]:
        """
        Perform health check.

        Returns dict with 'status' (ok/error) and optional details.
        """
        return 1


class DiskSpaceCheck(HealthCheck):
    """Check disk space availability."""

    def __init__(self, path: str = "/", min_free_gb: float = 1.0) -> None:
        self.path = path
        self.min_free_bytes = min_free_gb * 1024 * 1024 * 1024

    async def check(self) -> Dict[str, Any]:
        """Check disk space."""
        try:
            usage = psutil.disk_usage(self.path)
            free_gb = usage.free / (1024**3)

            if usage.free < self.min_free_bytes:
                return {
                    "status": "error",
                    "message": f"Low disk space: {free_gb:.2f}GB free",
                    "free_gb": free_gb,
                    "percent_used": usage.percent,
                }

            return {
                "status": "ok",
                "free_gb": free_gb,
                "percent_used": usage.percent,
            }
        except Exception as e:  # pylint: disable=broad-except
            return {"status": "error", "message": str(e)}


class MemoryCheck(HealthCheck):
    """Check memory usage."""

    def __init__(self, max_percent: float = 90.0) -> None:
        self.max_percent = max_percent

    async def check(self) -> Dict[str, Any]:
        """Check memory usage."""
        try:
            mem = psutil.virtual_memory()

            if mem.percent > self.max_percent:
                return {
                    "status": "error",
                    "message": f"High memory usage: {mem.percent}%",
                    "percent_used": mem.percent,
                    "available_gb": mem.available / (1024**3),
                }

            return {
                "status": "ok",
                "percent_used": mem.percent,
                "available_gb": mem.available / (1024**3),
            }
        except Exception as e:  # pylint: disable=broad-except
            return {"status": "error", "message": str(e)}


class DatabaseCheck(HealthCheck):
    """Check database connectivity."""

    def __init__(self, storage_backend: Any) -> None:
        self.storage = storage_backend

    async def check(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            # Try a simple operation
            now = datetime.datetime.now(datetime.timezone.utc)

            await self.storage.query_http_metrics(
                from_time=now - datetime.timedelta(seconds=1),
                to_time=now,
            )

            return {"status": "ok", "message": "Database connected"}
        except Exception as e:  # pylint: disable=broad-except
            return {"status": "error", "message": f"Database error: {str(e)}"}


class RedisCheck(HealthCheck):
    """Check Redis connectivity."""

    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client

    async def check(self) -> Dict[str, Any]:
        try:
            await self.redis.ping()
            return {"status": "ok", "message": "Redis connected"}
        except Exception as e:  # pylint: disable=broad-except
            return {"status": "error", "message": f"Redis error: {str(e)}"}
