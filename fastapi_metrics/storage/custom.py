"""Custom storage backends for FastAPI Metrics."""

import time
import json
from collections import defaultdict

try:
    import aioboto3
except ImportError:
    aioboto3 = None

try:
    import asyncpg
except ImportError:
    asyncpg = None

from .base import StorageBackend


class PostgreSQLStorage(StorageBackend):
    """PostgreSQL storage backend."""

    def __init__(self, connection_string: str):
        if asyncpg is None:
            raise ImportError(
                "PostgreSQL support requires 'asyncpg'. Install with: pip install asyncpg"
            )
        self.conn_str = connection_string
        self.pool = None

    async def initialize(self):
        self.pool = await asyncpg.create_pool(self.conn_str)

        async with self.pool.acquire() as conn:
            # HTTP metrics table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS http_metrics (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    labels JSONB
                )
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_http_timestamp ON http_metrics(timestamp)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_http_endpoint ON http_metrics(endpoint, method)
            """
            )

            # Errors table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS errors (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    error_message TEXT,
                    error_hash TEXT NOT NULL,
                    stack_trace TEXT,
                    user_agent TEXT,
                    count INTEGER DEFAULT 1,
                    first_seen TIMESTAMPTZ NOT NULL,
                    last_seen TIMESTAMPTZ NOT NULL,
                    UNIQUE(error_hash)
                )
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON errors(timestamp)
            """
            )

            # Custom metrics table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS custom_metrics (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ NOT NULL,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    labels JSONB
                )
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_custom_timestamp ON custom_metrics(timestamp)
            """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_custom_name ON custom_metrics(name)
            """
            )

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def store_http_metric(
        self, timestamp, endpoint, method, status_code, latency_ms, labels=None
    ):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO http_metrics (timestamp, endpoint, method, status_code, latency_ms, labels)
                VALUES ($1, $2, $3, $4, $5, $6)
            """,
                timestamp,
                endpoint,
                method,
                status_code,
                latency_ms,
                json.dumps(labels) if labels else None,
            )

    async def store_error(
        self,
        timestamp,
        endpoint,
        method,
        error_type,
        error_message,
        error_hash,
        stack_trace,
        user_agent=None,
    ):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO errors (
                    timestamp, endpoint, method, error_type, error_message,
                    error_hash, stack_trace, user_agent, first_seen, last_seen
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (error_hash) DO UPDATE SET
                    count = errors.count + 1,
                    last_seen = $10
            """,
                timestamp,
                endpoint,
                method,
                error_type,
                error_message,
                error_hash,
                stack_trace,
                user_agent,
                timestamp,
                timestamp,
            )

    async def store_custom_metric(self, timestamp, name, value, labels=None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO custom_metrics (timestamp, name, value, labels)
                VALUES ($1, $2, $3, $4)
            """,
                timestamp,
                name,
                value,
                json.dumps(labels) if labels else None,
            )

    async def query_http_metrics(
        self, from_time, to_time, endpoint=None, method=None, group_by=None
    ):
        query = "SELECT * FROM http_metrics WHERE timestamp BETWEEN $1 AND $2"
        params = [from_time, to_time]

        if endpoint:
            query += f" AND endpoint = ${len(params) + 1}"
            params.append(endpoint)
        if method:
            query += f" AND method = ${len(params) + 1}"
            params.append(method)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

            metrics = [dict(row) for row in rows]

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

    async def query_errors(self, from_time, to_time, endpoint=None):
        query = "SELECT * FROM errors WHERE timestamp BETWEEN $1 AND $2"
        params = [from_time, to_time]

        if endpoint:
            query += f" AND endpoint = ${len(params) + 1}"
            params.append(endpoint)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def query_custom_metrics(self, from_time, to_time, name=None, group_by=None):
        query = "SELECT * FROM custom_metrics WHERE timestamp BETWEEN $1 AND $2"
        params = [from_time, to_time]

        if name:
            query += f" AND name = ${len(params) + 1}"
            params.append(name)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            metrics = [dict(row) for row in rows]

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

    async def get_endpoint_stats(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    endpoint,
                    method,
                    COUNT(*) as count,
                    AVG(latency_ms) as avg_latency_ms,
                    MIN(latency_ms) as min_latency_ms,
                    MAX(latency_ms) as max_latency_ms,
                    SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as error_rate
                FROM http_metrics
                GROUP BY endpoint, method
            """
            )
            return [dict(row) for row in rows]

    async def cleanup_old_data(self, before):
        async with self.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM http_metrics WHERE timestamp < $1", before)
            deleted = int(result.split()[-1])

            result = await conn.execute("DELETE FROM custom_metrics WHERE timestamp < $1", before)
            deleted += int(result.split()[-1])

            result = await conn.execute("DELETE FROM errors WHERE timestamp < $1", before)
            deleted += int(result.split()[-1])

            return deleted


class DynamoDBStorage(StorageBackend):
    """DynamoDB storage backend."""

    def __init__(self, table_name: str, region: str = "us-east-1"):
        if aioboto3 is None:
            raise ImportError(
                "DynamoDB support requires 'aioboto3'. Install with: pip install aioboto3"
            )
        self.table_name = table_name
        self.region = region
        self.client = None
        self.session = None

    async def initialize(self):
        self.session = aioboto3.Session()
        self.client = await self.session.client("dynamodb", region_name=self.region).__aenter__()

    async def close(self):
        if self.client:
            await self.client.__aexit__(None, None, None)

    async def store_http_metric(
        self, timestamp, endpoint, method, status_code, latency_ms, labels=None
    ):
        ts = int(timestamp.timestamp() * 1000)
        item = {
            "PK": {"S": f"HTTP#{endpoint}#{method}"},
            "SK": {"N": str(ts)},
            "endpoint": {"S": endpoint},
            "method": {"S": method},
            "status_code": {"N": str(status_code)},
            "latency_ms": {"N": str(latency_ms)},
            "ttl": {"N": str(int(time.time()) + 86400 * 7)},
        }
        if labels:
            item["labels"] = {"S": json.dumps(labels)}

        await self.client.put_item(TableName=self.table_name, Item=item)

    async def store_error(
        self,
        timestamp,
        endpoint,
        method,
        error_type,
        error_message,
        error_hash,
        stack_trace,
        user_agent=None,
    ):
        ts = int(timestamp.timestamp() * 1000)
        item = {
            "PK": {"S": f"ERROR#{error_hash}"},
            "SK": {"N": str(ts)},
            "endpoint": {"S": endpoint},
            "method": {"S": method},
            "error_type": {"S": error_type},
            "error_message": {"S": error_message},
            "stack_trace": {"S": stack_trace},
            "count": {"N": "1"},
            "ttl": {"N": str(int(time.time()) + 86400 * 7)},
        }
        if user_agent:
            item["user_agent"] = {"S": user_agent}

        await self.client.put_item(TableName=self.table_name, Item=item)

    async def store_custom_metric(self, timestamp, name, value, labels=None):
        ts = int(timestamp.timestamp() * 1000)
        item = {
            "PK": {"S": f"CUSTOM#{name}"},
            "SK": {"N": str(ts)},
            "name": {"S": name},
            "value": {"N": str(value)},
            "ttl": {"N": str(int(time.time()) + 86400 * 7)},
        }
        if labels:
            item["labels"] = {"S": json.dumps(labels)}

        await self.client.put_item(TableName=self.table_name, Item=item)

    async def query_http_metrics(
        self, from_time, to_time, endpoint=None, method=None, group_by=None
    ):
        # DynamoDB query implementation - simplified
        # In production, use proper GSI and query patterns
        return []

    async def query_errors(self, from_time, to_time, endpoint=None):
        return []

    async def query_custom_metrics(self, from_time, to_time, name=None, group_by=None):
        return []

    async def get_endpoint_stats(self):
        return []

    async def cleanup_old_data(self, before):
        # DynamoDB uses TTL for automatic cleanup
        return 0
