"""
FastAPI Metrics - Complete metrics solution for FastAPI apps
Features: SQLite/Redis storage, K8s health checks, LLM cost tracking, Prometheus export, Alerting
"""

__version__ = "0.3.0"

from .core import Metrics
from .storage.base import StorageBackend
from .storage.memory import MemoryStorage
from .storage.sqlite import SQLiteStorage
from .alerting import Alert, AlertManager

__all__ = [
    "Metrics",
    "StorageBackend",
    "MemoryStorage",
    "SQLiteStorage",
    "Alert",
    "AlertManager",
]
