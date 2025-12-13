"""System metrics collection (CPU, Memory, Disk)."""

import time
from typing import Any, Dict
import psutil


class SystemMetricsCollector:
    """Collect system resource metrics."""

    def __init__(self, metrics_instance: Any) -> None:
        self.metrics = metrics_instance
        self.start_time = time.time()

    async def collect(self) -> Dict[str, Any]:
        """Collect current system metrics - RETURNS dict for /metrics endpoint"""
        return {
            "cpu_percent": round(psutil.cpu_percent(interval=0.1), 2),
            "memory_percent": round(psutil.virtual_memory().percent, 2),
            "memory_used_mb": round(psutil.virtual_memory().used / (1024 * 1024), 2),
            "memory_available_mb": round(psutil.virtual_memory().available / (1024 * 1024), 2),
            "disk_percent": round(psutil.disk_usage("/").percent, 2),
            "disk_used_gb": round(psutil.disk_usage("/").used / (1024**3), 2),
            "disk_free_gb": round(psutil.disk_usage("/").free / (1024**3), 2),
            "uptime_seconds": int(time.time() - self.start_time),
        }

    def get_cpu_percent(self) -> float:
        """For /metrics/system endpoint"""
        return psutil.cpu_percent(interval=0.1)

    def get_memory_stats(self) -> Dict[str, float]:
        """For /metrics/system endpoint"""
        mem = psutil.virtual_memory()
        return {
            "percent": mem.percent,
            "available_gb": mem.available / (1024**3),
            "used_gb": mem.used / (1024**3),
            "total_gb": mem.total / (1024**3),
        }

    def get_disk_stats(self, path: str = "/") -> Dict[str, float]:
        """For /metrics/system endpoint"""
        disk = psutil.disk_usage(path)
        return {
            "percent": disk.percent,
            "free_gb": disk.free / (1024**3),
            "used_gb": disk.used / (1024**3),
            "total_gb": disk.total / (1024**3),
        }

    async def collect_and_track(self):
        """Optional: Store system metrics as custom metrics for historical tracking"""
        cpu_percent = self.get_cpu_percent()
        await self.metrics.track("system_cpu_percent", cpu_percent)

        mem_stats = self.get_memory_stats()
        await self.metrics.track("system_memory_percent", mem_stats["percent"])
        await self.metrics.track("system_memory_available_gb", mem_stats["available_gb"])

        disk_stats = self.get_disk_stats()
        await self.metrics.track("system_disk_percent", disk_stats["percent"])
        await self.metrics.track("system_disk_free_gb", disk_stats["free_gb"])
