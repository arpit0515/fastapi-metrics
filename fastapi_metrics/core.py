from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from fastapi import FastAPI
import json

from .storage.base import StorageBackend
from .storage.memory import MemoryStorage
from .storage.sqlite import SQLiteStorage
from .middleware import MetricsMiddleware
from .health.endpoints import HealthManager
from .health.checks import DiskSpaceCheck, MemoryCheck, DatabaseCheck


class Metrics:
    """Main metrics class for FastAPI applications."""

    def __init__(
        self,
        app: FastAPI,
        storage: Union[str, StorageBackend] = "memory://",
        retention_hours: int = 24,
        enable_cleanup: bool = True,
        enable_health_checks: bool = False,
    ):
        """
        Initialize metrics for a FastAPI application.
        
        Args:
            app: FastAPI application instance
            storage: Storage backend ("memory://", "sqlite://path", "redis://host:port/db") or StorageBackend instance
            retention_hours: How long to keep metrics data (hours)
            enable_cleanup: Whether to enable automatic cleanup of old data
            enable_health_checks: Enable Kubernetes health check endpoints
        """
        self.app = app
        self.retention_hours = retention_hours
        self.enable_cleanup = enable_cleanup
        self._active_requests = 0
        self.health_manager = HealthManager() if enable_health_checks else None
        
        # Initialize storage backend
        if isinstance(storage, str):
            if storage.startswith("memory://"):
                self.storage = MemoryStorage()
            elif storage.startswith("sqlite://"):
                db_path = storage.replace("sqlite://", "")
                self.storage = SQLiteStorage(db_path)
            elif storage.startswith("redis://"):
                from .storage.redis import RedisStorage
                self.storage = RedisStorage(storage)
            else:
                raise ValueError(f"Unknown storage backend: {storage}")
        else:
            self.storage = storage
        
        # Register startup/shutdown events
        @app.on_event("startup")
        async def startup():
            await self.storage.initialize()
            
            # Setup health checks if enabled
            if self.health_manager:
                self.health_manager.add_check("disk", DiskSpaceCheck())
                self.health_manager.add_check("memory", MemoryCheck())
                self.health_manager.add_check("database", DatabaseCheck(self.storage))
                
                # Add Redis check if using Redis storage
                if storage.startswith("redis://"):
                    from .health.checks import RedisCheck
                    self.health_manager.add_check("redis", RedisCheck(self.storage.client))
        
        @app.on_event("shutdown")
        async def shutdown():
            await self.storage.close()
        
        # Add middleware
        app.add_middleware(MetricsMiddleware, metrics_instance=self)
        
        # Register metrics endpoints
        self._register_endpoints()

    def _register_endpoints(self):
        """Register metrics API endpoints."""
        
        @self.app.get("/metrics")
        async def get_metrics():
            """Get current metrics snapshot."""
            return {
                "active_requests": self._active_requests,
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        @self.app.get("/metrics/query")
        async def query_metrics(
            metric_type: str = "http",
            from_hours: int = 24,
            to_hours: int = 0,
            endpoint: Optional[str] = None,
            method: Optional[str] = None,
            name: Optional[str] = None,
            group_by: Optional[str] = None,
        ):
            """
            Query metrics with time range and filters.
            
            Args:
                metric_type: "http" or "custom"
                from_hours: Hours ago to start query (default: 24)
                to_hours: Hours ago to end query (default: 0 = now)
                endpoint: Filter by endpoint (HTTP only)
                method: Filter by method (HTTP only)
                name: Filter by metric name (custom only)
                group_by: Group results by "hour" or None
            """
            now = datetime.utcnow()
            from_time = now - timedelta(hours=from_hours)
            to_time = now - timedelta(hours=to_hours)
            
            if metric_type == "http":
                results = await self.storage.query_http_metrics(
                    from_time=from_time,
                    to_time=to_time,
                    endpoint=endpoint,
                    method=method,
                    group_by=group_by,
                )
            elif metric_type == "custom":
                results = await self.storage.query_custom_metrics(
                    from_time=from_time,
                    to_time=to_time,
                    name=name,
                    group_by=group_by,
                )
            else:
                return {"error": "Invalid metric_type. Use 'http' or 'custom'"}
            
            return {
                "metric_type": metric_type,
                "from": from_time.isoformat(),
                "to": to_time.isoformat(),
                "count": len(results),
                "results": results,
            }
        
        @self.app.get("/metrics/endpoints")
        async def get_endpoint_stats():
            """Get aggregated statistics per endpoint."""
            stats = await self.storage.get_endpoint_stats()
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "endpoints": stats,
            }
        
        @self.app.post("/metrics/cleanup")
        async def cleanup_metrics(hours_to_keep: int = None):
            """Manually trigger cleanup of old metrics data."""
            hours = hours_to_keep or self.retention_hours
            before = datetime.utcnow() - timedelta(hours=hours)
            deleted = await self.storage.cleanup_old_data(before)
            return {
                "deleted_records": deleted,
                "cleaned_before": before.isoformat(),
            }
        
        # Health check endpoints (if enabled)
        if self.health_manager:
            @self.app.get("/health")
            async def health():
                """Simple health check."""
                return await self.health_manager.run_checks()
            
            @self.app.get("/health/live")
            async def health_live():
                """Kubernetes liveness probe."""
                return await self.health_manager.liveness()
            
            @self.app.get("/health/ready")
            async def health_ready():
                """Kubernetes readiness probe."""
                result = await self.health_manager.readiness()
                # Return 503 if not ready
                from fastapi import Response
                status_code = 200 if result["status"] == "ok" else 503
                return Response(
                    content=json.dumps(result),
                    status_code=status_code,
                    media_type="application/json"
                )

    async def _store_http_metric(
        self,
        timestamp: datetime,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
    ):
        """Internal method to store HTTP metrics."""
        await self.storage.store_http_metric(
            timestamp=timestamp,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            latency_ms=latency_ms,
        )

    async def track(
        self,
        name: str,
        value: float,
        **labels: Any,
    ):
        """
        Track a custom business metric.
        
        Args:
            name: Metric name (e.g., "revenue", "signups", "api_calls")
            value: Numeric value to track
            **labels: Optional labels for segmentation (e.g., user_id=123, plan="pro")
        
        Example:
            await metrics.track("revenue", 99.99, user_id=123, plan="pro")
            await metrics.track("signups", 1, source="organic")
        """
        await self.storage.store_custom_metric(
            timestamp=datetime.utcnow(),
            name=name,
            value=value,
            labels=labels if labels else None,
        )

    def track_sync(self, name: str, value: float, **labels: Any):
        """
        Synchronous wrapper for track() - for use in non-async contexts.
        Note: This creates a new event loop. Use async track() when possible.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.track(name, value, **labels))
