"""SQLite storage backend for FastAPI Metrics."""

import datetime
import json
from typing import Any, Dict, List, Optional
from pathlib import Path
import aiosqlite

from .base import StorageBackend


class SQLiteStorage(StorageBackend):
    """SQLite storage backend for persistent metrics."""

    def __init__(self, db_path: str = "metrics.db"):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize SQLite database and create tables."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.db_path)

        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS http_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                latency_ms REAL NOT NULL,
                labels TEXT
            )
        """
        )

        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                name TEXT NOT NULL,
                value REAL NOT NULL,
                labels TEXT
            )
        """
        )

        # Indexes for query performance
        await self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_http_timestamp ON http_requests(timestamp)"
        )
        await self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_http_endpoint ON http_requests(endpoint)"
        )
        await self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_custom_timestamp ON custom_metrics(timestamp)"
        )
        await self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_custom_name ON custom_metrics(name)"
        )

        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT,
                error_hash TEXT NOT NULL,
                stack_trace TEXT,
                user_agent TEXT,
                count INTEGER DEFAULT 1,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """
        )

        await self.conn.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self.conn:
            await self.conn.close()

    async def store_http_metric(
        self,
        timestamp: datetime,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        labels: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store HTTP metric in SQLite."""
        if self.conn is None:
            await self.initialize()

        await self.conn.execute(
            """
            INSERT INTO http_requests 
            (timestamp, endpoint, method, status_code, latency_ms, labels)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp.timestamp(),
                endpoint,
                method,
                status_code,
                latency_ms,
                json.dumps(labels) if labels else None,
            ),
        )
        await self.conn.commit()

    async def store_custom_metric(
        self,
        timestamp: datetime,
        name: str,
        value: float,
        labels: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store custom metric in SQLite."""
        if self.conn is None:
            await self.initialize()

        await self.conn.execute(
            """
            INSERT INTO custom_metrics 
            (timestamp, name, value, labels)
            VALUES (?, ?, ?, ?)
            """,
            (
                timestamp.timestamp(),
                name,
                value,
                json.dumps(labels) if labels else None,
            ),
        )
        await self.conn.commit()

    async def query_http_metrics(
        self,
        from_time: datetime,
        to_time: datetime,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query HTTP metrics from SQLite."""
        if self.conn is None:
            await self.initialize()

        conditions = ["timestamp BETWEEN ? AND ?"]
        params = [from_time.timestamp(), to_time.timestamp()]

        if endpoint:
            conditions.append("endpoint = ?")
            params.append(endpoint)

        if method:
            conditions.append("method = ?")
            params.append(method)

        where_clause = " AND ".join(conditions)

        if group_by == "hour":
            # Group by hour using SQLite's datetime functions
            query = f"""
                SELECT 
                    strftime('%Y-%m-%d %H:00:00', datetime(timestamp, 'unixepoch')) as hour,
                    COUNT(*) as count,
                    AVG(latency_ms) as avg_latency_ms,
                    MIN(latency_ms) as min_latency_ms,
                    MAX(latency_ms) as max_latency_ms
                FROM http_requests
                WHERE {where_clause}
                GROUP BY hour
                ORDER BY hour
            """
        else:
            query = f"""
                SELECT timestamp, endpoint, method, status_code, latency_ms, labels
                FROM http_requests
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT 1000
            """

        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()

        if group_by == "hour":
            return [
                {
                    "timestamp": row[0],
                    "count": row[1],
                    "avg_latency_ms": row[2],
                    "min_latency_ms": row[3],
                    "max_latency_ms": row[4],
                }
                for row in rows
            ]

        return [
            {
                "timestamp": datetime.datetime.fromtimestamp(row[0]),
                "endpoint": row[1],
                "method": row[2],
                "status_code": row[3],
                "latency_ms": row[4],
                "labels": json.loads(row[5]) if row[5] else {},
            }
            for row in rows
        ]

    async def query_custom_metrics(
        self,
        from_time: datetime,
        to_time: datetime,
        name: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query custom metrics from SQLite."""
        if self.conn is None:
            await self.initialize()

        conditions = ["timestamp BETWEEN ? AND ?"]
        params = [from_time.timestamp(), to_time.timestamp()]

        if name:
            conditions.append("name = ?")
            params.append(name)

        where_clause = " AND ".join(conditions)

        if group_by == "hour":
            query = f"""
                SELECT 
                    strftime('%Y-%m-%d %H:00:00', datetime(timestamp, 'unixepoch')) as hour,
                    name,
                    COUNT(*) as count,
                    SUM(value) as sum,
                    AVG(value) as avg
                FROM custom_metrics
                WHERE {where_clause}
                GROUP BY hour, name
                ORDER BY hour
            """
        else:
            query = f"""
                SELECT timestamp, name, value, labels
                FROM custom_metrics
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT 1000
            """

        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()

        if group_by == "hour":
            return [
                {
                    "timestamp": row[0],
                    "name": row[1],
                    "count": row[2],
                    "sum": row[3],
                    "avg": row[4],
                }
                for row in rows
            ]

        return [
            {
                "timestamp": datetime.datetime.fromtimestamp(row[0]),
                "name": row[1],
                "value": row[2],
                "labels": json.loads(row[3]) if row[3] else {},
            }
            for row in rows
        ]

    async def get_endpoint_stats(self) -> List[Dict[str, Any]]:
        """Get aggregated statistics per endpoint."""
        if self.conn is None:
            await self.initialize()

        query = """
            SELECT 
                endpoint,
                method,
                COUNT(*) as count,
                AVG(latency_ms) as avg_latency_ms,
                MIN(latency_ms) as min_latency_ms,
                MAX(latency_ms) as max_latency_ms,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as error_rate
            FROM http_requests
            GROUP BY endpoint, method
            ORDER BY count DESC
        """

        cursor = await self.conn.execute(query)
        rows = await cursor.fetchall()

        return [
            {
                "endpoint": row[0],
                "method": row[1],
                "count": row[2],
                "avg_latency_ms": row[3],
                "min_latency_ms": row[4],
                "max_latency_ms": row[5],
                "error_rate": row[6],
            }
            for row in rows
        ]

    async def cleanup_old_data(self, before: datetime) -> int:
        """Remove data older than specified datetime.datetime."""
        if self.conn is None:
            await self.initialize()

        timestamp = before.timestamp()

        cursor = await self.conn.execute(
            "DELETE FROM http_requests WHERE timestamp < ?", (timestamp,)
        )
        http_deleted = cursor.rowcount

        cursor = await self.conn.execute(
            "DELETE FROM custom_metrics WHERE timestamp < ?", (timestamp,)
        )
        custom_deleted = cursor.rowcount

        await self.conn.commit()

        return http_deleted + custom_deleted
