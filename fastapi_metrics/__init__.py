"""
FastAPI Metrics - Zero-config metrics for FastAPI apps
Perfect for solo developers and MVPs on single-instance deployments.
"""

__version__ = "0.1.0"

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
