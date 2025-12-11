"""Prometheus export format."""

from typing import Any
import datetime


class PrometheusExporter:
    """Export metrics in Prometheus format."""

    def __init__(self, storage: Any) -> None:
        self.storage = storage

    async def export_http_metrics(self, hours: int = 1) -> str:
        """Export HTTP metrics in Prometheus format."""
        now = datetime.datetime.now(datetime.timezone.utc)
        _ = now - datetime.timedelta(hours=hours)

        # Get endpoint stats
        stats = await self.storage.get_endpoint_stats()

        lines = []

        # Request count
        lines.append("# HELP http_requests_total Total HTTP requests")
        lines.append("# TYPE http_requests_total counter")
        for stat in stats:
            endpoint = stat["endpoint"].replace('"', '\\"')
            method = stat["method"]
            lines.append(
                f'http_requests_total{{endpoint="{endpoint}",'
                f'method="{method}"}} {stat["count"]}'
            )

        # Latency
        lines.append("")
        lines.append("# HELP http_request_duration_ms HTTP request duration in ms")
        lines.append("# TYPE http_request_duration_ms gauge")
        for stat in stats:
            endpoint = stat["endpoint"].replace('"', '\\"')
            method = stat["method"]
            lines.append(
                f'http_request_duration_ms{{endpoint="{endpoint}",'
                f'method="{method}",quantile="avg"}} {stat["avg_latency_ms"]}'
            )

        # Error rate
        lines.append("")
        lines.append("# HELP http_error_rate HTTP error rate (0-1)")
        lines.append("# TYPE http_error_rate gauge")
        for stat in stats:
            endpoint = stat["endpoint"].replace('"', '\\"')
            method = stat["method"]
            lines.append(
                f'http_error_rate{{endpoint="{endpoint}",method="{method}"}} {stat["error_rate"]}'
            )

        return "\n".join(lines)

    async def export_custom_metrics(self, hours: int = 1) -> str:
        """Export custom metrics in Prometheus format."""
        now = datetime.datetime.now(datetime.timezone.utc)
        from_time = now - datetime.timedelta(hours=hours)

        # Get custom metrics
        metrics = await self.storage.query_custom_metrics(
            from_time=from_time,
            to_time=now,
        )

        # Group by metric name
        by_name = {}
        for m in metrics:
            name = m["name"]
            if name not in by_name:
                by_name[name] = []
            by_name[name].append(m)

        lines = []

        for name, values in by_name.items():
            # Calculate sum
            total = sum(v["value"] for v in values)

            lines.append(f"# HELP {name} Custom metric: {name}")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {total}")

        return "\n".join(lines)

    async def export_all(self, hours: int = 1) -> str:
        """Export all metrics in Prometheus format."""
        http_metrics = await self.export_http_metrics(hours)
        custom_metrics = await self.export_custom_metrics(hours)

        return f"{http_metrics}\n\n{custom_metrics}"
