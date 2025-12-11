"""Simple threshold-based alerting with webhook notifications."""

import asyncio
import logging
from typing import Optional, Dict, Any
import datetime

logger = logging.getLogger(__name__)

try:
    import httpx
except ImportError:
    httpx = None


class Alert:
    """Alert configuration."""

    def __init__(
        self,
        name: str,
        metric_name: str,
        threshold: float,
        comparison: str = ">",  # >, <, >=, <=, ==
        window_minutes: int = 5,
    ):
        self.name = name
        self.metric_name = metric_name
        self.threshold = threshold
        self.comparison = comparison
        self.window_minutes = window_minutes
        self.last_triggered = None

    def check(self, value: float) -> bool:
        """Check if alert should trigger."""
        if self.comparison == ">":
            return value > self.threshold
        if self.comparison == "<":
            return value < self.threshold
        if self.comparison == ">=":
            return value >= self.threshold
        if self.comparison == "<=":
            return value <= self.threshold
        if self.comparison == "==":
            return value == self.threshold
        return False


class AlertManager:
    """Manage alerts and notifications."""

    def __init__(self, metrics_instance: Any, webhook_url: Optional[str] = None) -> None:
        self.metrics = metrics_instance
        self.webhook_url = webhook_url
        self.alerts: Dict[str, Alert] = {}
        self._running = False
        self._task = None

    def __del__(self):
        """Ensure background task is stopped on cleanup."""
        if self._running and self._task:
            # Can't await in destructor, so just cancel
            self._task.cancel()
            self._running = False

    def add_alert(self, alert: Alert):
        """Register an alert."""
        self.alerts[alert.name] = alert

    def remove_alert(self, name: str):
        """Remove an alert."""
        if name in self.alerts:
            del self.alerts[name]

    async def check_alerts(self):
        """Check all alerts against current metrics."""
        now = datetime.datetime.now(datetime.timezone.utc)

        for alert in self.alerts.values():
            # Skip if recently triggered (avoid spam)
            if alert.last_triggered:
                time_since = (now - alert.last_triggered).total_seconds() / 60
                if time_since < alert.window_minutes:
                    continue

            # Query metric
            from_time = now - datetime.timedelta(minutes=alert.window_minutes)
            metrics = await self.metrics.storage.query_custom_metrics(
                from_time=from_time,
                to_time=now,
                name=alert.metric_name,
            )

            if not metrics:
                continue

            # Calculate average value in window
            avg_value = sum(m["value"] for m in metrics) / len(metrics)

            # Check threshold
            if alert.check(avg_value):
                await self._trigger_alert(alert, avg_value)
                alert.last_triggered = now

    async def _trigger_alert(self, alert: Alert, value: float):
        """Trigger an alert."""
        message = {
            "alert": alert.name,
            "metric": alert.metric_name,
            "value": value,
            "threshold": alert.threshold,
            "comparison": alert.comparison,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        # Send webhook
        if self.webhook_url and httpx:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        self.webhook_url,
                        json=message,
                    )
            except Exception as e:  # pylint: disable=broad-except
                # Log error but don't fail
                logger.error("Failed to send alert webhook: %s", e)

        # Track alert as metric
        await self.metrics.track(
            "alert_triggered",
            1,
            alert_name=alert.name,
            metric_name=alert.metric_name,
        )

    async def _check_loop(self):
        """Background task to check alerts periodically."""
        while self._running:
            try:
                await self.check_alerts()
            except Exception as e:  # pylint: disable=broad-except
                logger.error("Error checking alerts: %s", e)

            # Check every minute
            await asyncio.sleep(60)

    def start(self):
        """Start the alert checking background task."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._check_loop())

    async def stop(self):
        """Stop the alert checking background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
