"""Health check endpoint management."""

from typing import Any, Dict
from .checks import HealthCheck


class HealthManager:
    """Manage health checks and provide endpoints."""

    def __init__(self) -> None:
        self.checks: Dict[str, HealthCheck] = {}

    def add_check(self, name: str, check: HealthCheck) -> None:
        """Register a health check."""
        self.checks[name] = check

    async def run_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {}
        overall_status = "ok"

        for name, check in self.checks.items():
            result = await check.check()
            results[name] = result

            if result.get("status") != "ok":
                overall_status = "error"

        return {
            "status": overall_status,
            "checks": results,
        }

    async def liveness(self) -> Dict[str, str]:
        """Kubernetes liveness probe - is the app running?"""
        return {"status": "ok"}

    async def readiness(self) -> Dict[str, Any]:
        """Kubernetes readiness probe - can the app serve traffic?"""
        return await self.run_checks()
