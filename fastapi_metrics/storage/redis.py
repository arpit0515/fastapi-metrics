""" "Redis storage backend for FastAPI Metrics."""

from collections import defaultdict
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

from .base import StorageBackend


class RedisStorage(StorageBackend):
    """Redis storage backend for distributed/multi-instance deployments."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        if redis is None:
            raise ImportError(
                "Redis support requires 'redis' package. Install with: pip install redis"
            )

        self.redis_url = redis_url
        self.client: Optional[Any] | None = None

        # Parse URL for connection
        parsed = urlparse(redis_url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 6379
        self.db = int(parsed.path.strip("/") or 0)
        self.password = parsed.password

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        self.client = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            decode_responses=True,
        )

        # Test connection
        await self.client.ping()

    async def close(self) -> None:
        """Close Redis connection."""
        if self.client:
            await self.client.close()

    async def store_http_metric(
        self,
        timestamp: datetime,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        labels: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store HTTP metric in Redis using sorted sets and hashes."""
        metric_id = f"http:{timestamp.timestamp()}"

        # Store metric data as hash
        await self.client.hset(
            metric_id,
            mapping={
                "timestamp": timestamp.timestamp(),
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "labels": json.dumps(labels) if labels else "{}",
            },
        )

        # Add to sorted set for time-based queries
        await self.client.zadd("http_metrics", {metric_id: timestamp.timestamp()})

        # Add to endpoint-specific sorted set
        endpoint_key = f"http:endpoint:{endpoint}:{method}"
        await self.client.zadd(endpoint_key, {metric_id: timestamp.timestamp()})

        # Expire individual metrics after 7 days
        await self.client.expire(metric_id, 604800)

    async def store_custom_metric(
        self,
        timestamp: datetime,
        name: str,
        value: float,
        labels: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store custom metric in Redis."""
        metric_id = f"custom:{name}:{timestamp.timestamp()}"

        # Store metric data
        await self.client.hset(
            metric_id,
            mapping={
                "timestamp": timestamp.timestamp(),
                "name": name,
                "value": value,
                "labels": json.dumps(labels) if labels else "{}",
            },
        )

        # Add to sorted set for queries
        await self.client.zadd("custom_metrics", {metric_id: timestamp.timestamp()})
        await self.client.zadd(f"custom:{name}", {metric_id: timestamp.timestamp()})

        # Expire after 7 days
        await self.client.expire(metric_id, 604800)

    async def query_http_metrics(
        self,
        from_time: datetime,
        to_time: datetime,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query HTTP metrics from Redis."""
        # Determine which sorted set to query
        if endpoint and method:
            key = f"http:endpoint:{endpoint}:{method}"
        else:
            key = "http_metrics"

        # Get metric IDs in time range
        metric_ids = await self.client.zrangebyscore(
            key,
            from_time.timestamp(),
            to_time.timestamp(),
        )

        if not metric_ids:
            return []

        # Fetch all metrics (pipeline for performance)
        pipeline = self.client.pipeline()
        for metric_id in metric_ids:
            pipeline.hgetall(metric_id)

        results = await pipeline.execute()

        # Parse results
        metrics = []
        for data in results:
            if not data:
                continue

            metric = {
                "timestamp": datetime.fromtimestamp(float(data["timestamp"])),
                "endpoint": data["endpoint"],
                "method": data["method"],
                "status_code": int(data["status_code"]),
                "latency_ms": float(data["latency_ms"]),
                "labels": json.loads(data.get("labels", "{}")),
            }

            # Apply filters
            if endpoint and metric["endpoint"] != endpoint:
                continue
            if method and metric["method"] != method:
                continue

            metrics.append(metric)

        # Group by hour if requested
        if group_by == "hour":
            grouped = defaultdict(list)

            for m in metrics:
                hour_key = m["timestamp"].replace(minute=0, second=0, microsecond=0)
                grouped[hour_key].append(m)

            return [
                {
                    "timestamp": str(k),
                    "count": len(v),
                    "avg_latency_ms": sum(x["latency_ms"] for x in v) / len(v),
                    "min_latency_ms": min(x["latency_ms"] for x in v),
                    "max_latency_ms": max(x["latency_ms"] for x in v),
                }
                for k, v in sorted(grouped.items())
            ]

        return metrics

    async def query_custom_metrics(
        self,
        from_time: datetime,
        to_time: datetime,
        name: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query custom metrics from Redis."""
        # Use name-specific key if provided
        key = f"custom:{name}" if name else "custom_metrics"

        # Get metric IDs
        metric_ids = await self.client.zrangebyscore(
            key,
            from_time.timestamp(),
            to_time.timestamp(),
        )

        if not metric_ids:
            return []

        # Fetch metrics
        pipeline = self.client.pipeline()
        for metric_id in metric_ids:
            pipeline.hgetall(metric_id)

        results = await pipeline.execute()

        # Parse results
        metrics = []
        for data in results:
            if not data:
                continue

            metric = {
                "timestamp": datetime.fromtimestamp(float(data["timestamp"])),
                "name": data["name"],
                "value": float(data["value"]),
                "labels": json.loads(data.get("labels", "{}")),
            }

            if name and metric["name"] != name:
                continue

            metrics.append(metric)

        # Group by hour
        if group_by == "hour":
            grouped = defaultdict(list)

            for m in metrics:
                hour_key = m["timestamp"].replace(minute=0, second=0, microsecond=0)
                grouped[hour_key].append(m)

            return [
                {
                    "timestamp": str(k),
                    "name": v[0]["name"],
                    "count": len(v),
                    "sum": sum(x["value"] for x in v),
                    "avg": sum(x["value"] for x in v) / len(v),
                }
                for k, v in sorted(grouped.items())
            ]

        return metrics

    async def get_endpoint_stats(self) -> List[Dict[str, Any]]:
        """Get aggregated statistics per endpoint."""
        # Get all endpoint keys
        endpoint_keys = []
        cursor = "0"
        max_iterations = 100  # Safety limit
        iterations = 0

        while iterations < max_iterations:
            iterations += 1
            cursor, keys = await self.client.scan(cursor, match="http:endpoint:*", count=100)
            endpoint_keys.extend(keys)
            if cursor in ("0", 0):
                break

        stats = []

        for key in endpoint_keys:
            # Parse endpoint and method from key
            parts = key.split(":")
            if len(parts) < 4:
                continue

            endpoint = parts[2]
            method = parts[3]

            # Get all metrics for this endpoint
            metric_ids = await self.client.zrange(key, 0, -1)

            if not metric_ids:
                continue

            # Fetch metrics
            pipeline = self.client.pipeline()
            for metric_id in metric_ids:
                pipeline.hgetall(metric_id)

            results = await pipeline.execute()

            latencies = []
            error_count = 0

            for data in results:
                if not data:
                    continue

                latencies.append(float(data["latency_ms"]))
                if int(data["status_code"]) >= 400:
                    error_count += 1

            if not latencies:
                continue

            latencies.sort()
            count = len(latencies)

            stats.append(
                {
                    "endpoint": endpoint,
                    "method": method,
                    "count": count,
                    "avg_latency_ms": sum(latencies) / count,
                    "min_latency_ms": min(latencies),
                    "max_latency_ms": max(latencies),
                    "error_rate": error_count / count if count > 0 else 0,
                }
            )

        return stats

    async def cleanup_old_data(self, before: datetime) -> int:
        """Remove data older than specified datetime."""
        timestamp = before.timestamp()
        deleted = 0

        # Clean HTTP metrics
        http_ids = await self.client.zrangebyscore("http_metrics", "-inf", timestamp)
        if http_ids:
            pipeline = self.client.pipeline()
            for metric_id in http_ids:
                pipeline.delete(metric_id)
            pipeline.zremrangebyscore("http_metrics", "-inf", timestamp)
            await pipeline.execute()
            deleted += len(http_ids)

        # Clean custom metrics
        custom_ids = await self.client.zrangebyscore("custom_metrics", "-inf", timestamp)
        if custom_ids:
            pipeline = self.client.pipeline()
            for metric_id in custom_ids:
                pipeline.delete(metric_id)
            pipeline.zremrangebyscore("custom_metrics", "-inf", timestamp)
            await pipeline.execute()
            deleted += len(custom_ids)

        return deleted
