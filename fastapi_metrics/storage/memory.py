"""In-memory storage backend for FastAPI Metrics."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict
import statistics

from .base import StorageBackend


class MemoryStorage(StorageBackend):
    """In-memory storage backend for development/testing."""

    def __init__(self):
        self.http_metrics: List[Dict[str, Any]] = []
        self.custom_metrics: List[Dict[str, Any]] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize in-memory storage."""
        self._initialized = True

    async def close(self) -> None:
        """Clear all data."""
        self.http_metrics.clear()
        self.custom_metrics.clear()
        self._initialized = False

    async def store_http_metric(
        self,
        timestamp: datetime,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        labels: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store HTTP metric in memory."""
        self.http_metrics.append(
            {
                "timestamp": timestamp,
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "labels": labels or {},
            }
        )

    async def store_custom_metric(
        self,
        timestamp: datetime,
        name: str,
        value: float,
        labels: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store custom metric in memory."""
        self.custom_metrics.append(
            {
                "timestamp": timestamp,
                "name": name,
                "value": value,
                "labels": labels or {},
            }
        )

    async def query_http_metrics(
        self,
        from_time: datetime,
        to_time: datetime,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query HTTP metrics from memory."""
        filtered = [
            m
            for m in self.http_metrics
            if from_time <= m["timestamp"] <= to_time
            and (endpoint is None or m["endpoint"] == endpoint)
            and (method is None or m["method"] == method)
        ]

        if not group_by:
            return filtered

        # Simple grouping by hour
        if group_by == "hour":
            grouped = defaultdict(list)
            for m in filtered:
                key = m["timestamp"].replace(minute=0, second=0, microsecond=0)
                grouped[key].append(m)

            return [
                {
                    "timestamp": k,
                    "count": len(v),
                    "avg_latency_ms": statistics.mean([x["latency_ms"] for x in v]),
                }
                for k, v in sorted(grouped.items())
            ]

        return filtered

    async def query_custom_metrics(
        self,
        from_time: datetime,
        to_time: datetime,
        name: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query custom metrics from memory."""
        filtered = [
            m
            for m in self.custom_metrics
            if from_time <= m["timestamp"] <= to_time and (name is None or m["name"] == name)
        ]

        if not group_by:
            return filtered

        # Simple grouping by hour
        if group_by == "hour":
            grouped = defaultdict(list)
            for m in filtered:
                key = m["timestamp"].replace(minute=0, second=0, microsecond=0)
                grouped[key].append(m)

            return [
                {
                    "timestamp": k,
                    "count": len(v),
                    "sum": sum(x["value"] for x in v),
                    "avg": statistics.mean([x["value"] for x in v]),
                }
                for k, v in sorted(grouped.items())
            ]

        return filtered

    async def get_endpoint_stats(self) -> List[Dict[str, Any]]:
        """Get aggregated stats per endpoint."""
        by_endpoint = defaultdict(list)
        for m in self.http_metrics:
            key = (m["endpoint"], m["method"])
            by_endpoint[key].append(m)

        stats = []
        for (endpoint, method), metrics in by_endpoint.items():
            latencies = [m["latency_ms"] for m in metrics]
            status_codes = [m["status_code"] for m in metrics]

            stats.append(
                {
                    "endpoint": endpoint,
                    "method": method,
                    "count": len(metrics),
                    "avg_latency_ms": statistics.mean(latencies),
                    "p50_latency_ms": statistics.median(latencies),
                    "p95_latency_ms": (
                        statistics.quantiles(latencies, n=20)[18]
                        if len(latencies) > 1
                        else latencies[0]
                    ),
                    "p99_latency_ms": (
                        statistics.quantiles(latencies, n=100)[98]
                        if len(latencies) > 1
                        else latencies[0]
                    ),
                    "error_rate": len([s for s in status_codes if s >= 400]) / len(status_codes),
                }
            )

        return stats

    async def cleanup_old_data(self, before: datetime) -> int:
        """Remove data older than specified datetime."""
        http_before = len(self.http_metrics)
        custom_before = len(self.custom_metrics)

        self.http_metrics = [m for m in self.http_metrics if m["timestamp"] >= before]
        self.custom_metrics = [m for m in self.custom_metrics if m["timestamp"] >= before]

        return (http_before - len(self.http_metrics)) + (custom_before - len(self.custom_metrics))
