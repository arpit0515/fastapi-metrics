"""
FastAPI Metrics - Zero-config metrics for FastAPI apps
Supports SQLite (single-instance) and Redis (multi-instance/K8s) storage.
"""

__version__ = "0.2.0"

from .core import Metrics
from .storage.base import StorageBackend
from .storage.memory import MemoryStorage
from .storage.sqlite import SQLiteStorage

__all__ = [
    "Metrics",
    "StorageBackend",
    "MemoryStorage",
    "SQLiteStorage",
]
