"""System metrics collection (CPU, Memory, Disk)."""

import psutil
from typing import Dict
from datetime import datetime


class SystemMetricsCollector:
    """Collect system resource metrics."""
    
    def __init__(self, metrics_instance):
        self.metrics = metrics_instance
    
    def get_cpu_percent(self) -> float:
        """Get current CPU usage percentage."""
        return psutil.cpu_percent(interval=0.1)
    
    def get_memory_stats(self) -> Dict[str, float]:
        """Get memory statistics."""
        mem = psutil.virtual_memory()
        return {
            "percent": mem.percent,
            "available_gb": mem.available / (1024 ** 3),
            "used_gb": mem.used / (1024 ** 3),
            "total_gb": mem.total / (1024 ** 3),
        }
    
    def get_disk_stats(self, path: str = "/") -> Dict[str, float]:
        """Get disk statistics."""
        disk = psutil.disk_usage(path)
        return {
            "percent": disk.percent,
            "free_gb": disk.free / (1024 ** 3),
            "used_gb": disk.used / (1024 ** 3),
            "total_gb": disk.total / (1024 ** 3),
        }
    
    async def collect_and_track(self):
        """Collect all system metrics and track them."""
        # CPU
        cpu_percent = self.get_cpu_percent()
        await self.metrics.track("system_cpu_percent", cpu_percent)
        
        # Memory
        mem_stats = self.get_memory_stats()
        await self.metrics.track("system_memory_percent", mem_stats["percent"])
        await self.metrics.track("system_memory_available_gb", mem_stats["available_gb"])
        
        # Disk
        disk_stats = self.get_disk_stats()
        await self.metrics.track("system_disk_percent", disk_stats["percent"])
        await self.metrics.track("system_disk_free_gb", disk_stats["free_gb"])
