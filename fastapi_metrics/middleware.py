import time
from datetime import datetime
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP request metrics."""

    def __init__(self, app, metrics_instance):
        super().__init__(app)
        self.metrics = metrics_instance

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track request metrics."""
        start_time = time.perf_counter()

        # Track active requests
        self.metrics._active_requests += 1

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Track errors
            status_code = 500
            self.metrics._active_requests -= 1
            raise e
        finally:
            # Calculate latency
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000

            # Store metric
            await self.metrics._store_http_metric(
                timestamp=datetime.utcnow(),
                endpoint=request.url.path,
                method=request.method,
                status_code=status_code,
                latency_ms=latency_ms,
            )

            self.metrics._active_requests -= 1

        return response
