"""Core metrics functionality for FastAPI applications."""

import datetime
from typing import Any, Optional, Union, Dict
import asyncio
import json
import statistics
from fastapi import FastAPI, Response
from .storage.base import StorageBackend
from .storage.redis import RedisStorage
from .storage.memory import MemoryStorage
from .storage.sqlite import SQLiteStorage
from .middleware import MetricsMiddleware
from .health.endpoints import HealthManager
from .health.checks import RedisCheck, DiskSpaceCheck, MemoryCheck, DatabaseCheck
from .collectors.llm_costs import LLMCostTracker
from .collectors.system import SystemMetricsCollector
from .exporters.prometheus import PrometheusExporter
from .alerting import AlertManager


class Metrics:
    """Main metrics class for FastAPI applications."""

    def __init__(
        self,
        app: FastAPI,
        storage: Union[str, StorageBackend] = "memory://",
        retention_hours: int = 24,
        enable_cleanup: bool = True,
        enable_health_checks: bool = False,
        enable_system_metrics: bool = False,
        alert_webhook_url: Optional[str] = None,
    ):
        """
        Initialize metrics for a FastAPI application.

        Args:
            app: FastAPI application instance
            storage: Storage backend ("memory://", "sqlite://path",
                "redis://host:port/db") or StorageBackend instance
            retention_hours: How long to keep metrics data (hours)
            enable_cleanup: Whether to enable automatic cleanup of old data
            enable_health_checks: Enable Kubernetes health check endpoints
            enable_system_metrics: Enable system metrics collection
                (CPU, memory, disk)
            alert_webhook_url: Optional webhook URL for alert notifications
        """
        self.app = app
        self.retention_hours = retention_hours
        self.enable_cleanup = enable_cleanup
        self._active_requests = 0
        self.health_manager = HealthManager() if enable_health_checks else None

        # Initialize Phase 3 components
        self.llm_costs = LLMCostTracker(self)
        self.system_metrics = SystemMetricsCollector(self) if enable_system_metrics else None
        self.alert_manager = AlertManager(self, webhook_url=alert_webhook_url)

        # Initialize storage backend
        if isinstance(storage, str):
            if storage.startswith("memory://"):
                self.storage = MemoryStorage()
            elif storage.startswith("sqlite://"):
                db_path = storage.replace("sqlite://", "")
                self.storage = SQLiteStorage(db_path)
            elif storage.startswith("redis://"):
                self.storage = RedisStorage(storage)
            else:
                raise ValueError(f"Unknown storage backend: {storage}")
        else:
            self.storage = storage

        # Register startup/shutdown handlers using explicit event registration
        # instead of the decorator `@app.on_event(...)`. This avoids relying
        # on the decorator form which may be deprecated in some contexts.
        async def startup():
            await self.storage.initialize()

            # Setup health checks if enabled
            if self.health_manager:
                self.health_manager.add_check("disk", DiskSpaceCheck())
                self.health_manager.add_check("memory", MemoryCheck())
                self.health_manager.add_check("database", DatabaseCheck(self.storage))

                # Add Redis check if using Redis storage. Guard against the
                # case where `storage` was provided as a StorageBackend
                # instance (not a string) so `.startswith()` would fail.
                if (isinstance(storage, str) and storage.startswith("redis://")) or isinstance(
                    self.storage, RedisStorage
                ):
                    self.health_manager.add_check("redis", RedisCheck(self.storage.client))

        async def shutdown():
            await self.storage.close()

        app.add_event_handler("startup", startup)
        app.add_event_handler("shutdown", shutdown)

        # Add middleware
        app.add_middleware(MetricsMiddleware, metrics_instance=self)

        # Register metrics endpoints
        self._register_endpoints()

    def _register_endpoints(self):
        """Register metrics API endpoints."""

        @self.app.get("/metrics")
        async def get_metrics() -> Dict[str, Any]:
            """Get current metrics snapshot with aggregations"""

            to_time = datetime.datetime.now(datetime.timezone.utc)
            from_time = to_time - datetime.timedelta(hours=24)

            # Use the correct storage method names
            http_data = await self.storage.query_http_metrics(
                from_time=from_time,
                to_time=to_time,
            )

            # Aggregate HTTP metrics
            total_requests = len(http_data)
            status_codes = {}
            endpoints = {}
            latencies = []
            error_count = 0

            for record in http_data:
                status = record.get("status_code", 0)
                status_codes[status] = status_codes.get(status, 0) + 1

                endpoint = record.get("endpoint", "unknown")
                method = record.get("method", "GET")
                key = f"{endpoint}:{method}"
                if key not in endpoints:
                    endpoints[key] = {"count": 0, "latencies": []}
                endpoints[key]["count"] += 1

                latency = record.get("latency_ms", 0)
                latencies.append(latency)
                endpoints[key]["latencies"].append(latency)

                if status >= 400:
                    error_count += 1

            def percentile(data, p):
                if not data:
                    return 0
                s = sorted(data)
                idx = int(len(s) * p / 100)
                return s[min(idx, len(s) - 1)]

            # Format endpoints
            requests_per_endpoint = {}
            for key, data in endpoints.items():
                ep, meth = key.split(":")
                if ep not in requests_per_endpoint:
                    requests_per_endpoint[ep] = {}
                requests_per_endpoint[ep][meth] = data["count"]

            # Build response
            metrics = {
                "http": {
                    "total_requests": total_requests,
                    "requests_per_endpoint": requests_per_endpoint,
                    "status_codes": status_codes,
                    "latency": {
                        "p50": round(percentile(latencies, 50), 2) if latencies else 0,
                        "p95": round(percentile(latencies, 95), 2) if latencies else 0,
                        "p99": round(percentile(latencies, 99), 2) if latencies else 0,
                        "avg": round(statistics.mean(latencies), 2) if latencies else 0,
                    },
                    "error_rate": (
                        round(error_count / total_requests, 3) if total_requests > 0 else 0
                    ),
                    "active_requests": self._active_requests,
                },
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            }

            # Add system metrics if enabled
            if self.system_metrics:
                system_data = await self.system_metrics.collect()
                metrics["system"] = system_data

            # Add custom metrics summary
            custom_data = await self.storage.query_custom_metrics(
                from_time=from_time,
                to_time=to_time,
            )

            if custom_data:
                custom_summary = {}
                for record in custom_data:
                    name = record.get("name") or record.get("metric_name", "unknown")
                    value = record.get("value", 0)

                    if name not in custom_summary:
                        custom_summary[name] = {
                            "count": 0,
                            "sum": 0,
                            "min": float("inf"),
                            "max": float("-inf"),
                        }

                    custom_summary[name]["count"] += 1
                    custom_summary[name]["sum"] += value
                    custom_summary[name]["min"] = min(custom_summary[name]["min"], value)
                    custom_summary[name]["max"] = max(custom_summary[name]["max"], value)

                for name, data in custom_summary.items():
                    data["avg"] = round(data["sum"] / data["count"], 2)
                    data["total"] = data["sum"]
                    del data["sum"]

                metrics["custom"] = custom_summary

            return metrics

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
            now = datetime.datetime.now(datetime.timezone.utc)
            from_time = now - datetime.timedelta(hours=from_hours)
            to_time = now - datetime.timedelta(hours=to_hours)

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
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "endpoints": stats,
            }

        @self.app.post("/metrics/cleanup")
        async def cleanup_metrics(hours_to_keep: int = None):
            """Manually trigger cleanup of old metrics data."""
            hours = hours_to_keep or self.retention_hours
            before = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
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
                status_code = 200 if result["status"] == "ok" else 503
                return Response(
                    content=json.dumps(result),
                    status_code=status_code,
                    media_type="application/json",
                )

        # Phase 3: System metrics endpoints (if enabled)
        if self.system_metrics:

            @self.app.get("/metrics/system")
            async def get_system_metrics():
                """Get current system metrics."""
                return {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "cpu_percent": self.system_metrics.get_cpu_percent(),
                    "memory": self.system_metrics.get_memory_stats(),
                    "disk": self.system_metrics.get_disk_stats(),
                }

        # Phase 3: LLM Costs endpoint
        @self.app.get("/metrics/costs")
        async def get_llm_costs(hours: int = 24):
            """Get LLM API costs."""
            now = datetime.datetime.now(datetime.timezone.utc)
            from_time = now - datetime.timedelta(hours=hours)

            costs = await self.storage.query_custom_metrics(
                from_time=from_time,
                to_time=now,
                name="llm_cost",
            )

            total_cost = sum(c.get("value", 0) for c in costs)
            by_provider = {}
            for cost in costs:
                provider = cost.get("labels", {}).get("provider", "unknown")
                if provider not in by_provider:
                    by_provider[provider] = 0
                by_provider[provider] += cost.get("value", 0)

            return {
                "total_cost": total_cost,
                "by_provider": by_provider,
                "count": len(costs),
                "period_hours": hours,
            }

        # Phase 3: Prometheus export endpoint
        @self.app.get("/metrics/export/prometheus")
        async def export_prometheus(hours: int = 1):
            """Export metrics in Prometheus format."""
            exporter = PrometheusExporter(self.storage)
            output = await exporter.export_http_metrics(hours=hours)
            return Response(
                content=output,
                media_type="text/plain; version=0.0.4",
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
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            name=name,
            value=value,
            labels=labels if labels else None,
        )

    def track_sync(self, name: str, value: float, **labels: Any):
        """
        Synchronous wrapper for track() - for use in non-async contexts.
        Note: This creates a new event loop. Use async track() when possible.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.track(name, value, **labels))

    async def init(self) -> None:
        """Initialize storage and (if enabled) register health checks.

        Useful when using `Metrics` outside the ASGI lifecycle (for
        example in scripts or tests) where the FastAPI startup event is
        not automatically executed.
        """
        await self.storage.initialize()

        if self.health_manager:
            self.health_manager.add_check("disk", DiskSpaceCheck())
            self.health_manager.add_check("memory", MemoryCheck())
            self.health_manager.add_check("database", DatabaseCheck(self.storage))
            if isinstance(self.storage, RedisStorage):
                self.health_manager.add_check("redis", RedisCheck(self.storage.client))

    def init_sync(self) -> None:
        """Synchronous helper to run `init()` from sync code.

        This creates/uses an event loop to run the async initialization.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.init())
