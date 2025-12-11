"""Abstract base class for metrics storage backends."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime


class StorageBackend(ABC):
    """Abstract base class for metrics storage backends."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize storage (create tables, connections, etc)."""
        return 1

    @abstractmethod
    async def close(self) -> None:
        """Close storage connections and cleanup."""
        return 1

    @abstractmethod
    async def store_http_metric(
        self,
        timestamp: datetime,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        labels: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store HTTP request metric."""
        return 1

    @abstractmethod
    async def store_custom_metric(
        self,
        timestamp: datetime,
        name: str,
        value: float,
        labels: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store custom business metric."""
        return 1

    @abstractmethod
    async def query_http_metrics(
        self,
        from_time: datetime,
        to_time: datetime,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query HTTP metrics within time range."""
        return 1

    @abstractmethod
    async def query_custom_metrics(
        self,
        from_time: datetime,
        to_time: datetime,
        name: Optional[str] = None,
        group_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query custom metrics within time range."""
        return 1

    @abstractmethod
    async def get_endpoint_stats(self) -> List[Dict[str, Any]]:
        """Get aggregated statistics per endpoint."""
        return 1

    @abstractmethod
    async def cleanup_old_data(self, before: datetime) -> int:
        """Remove data older than specified datetime. Returns count of deleted records."""
        return 1
