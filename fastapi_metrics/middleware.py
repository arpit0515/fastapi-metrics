"""Middleware for tracking HTTP request metrics."""

import time
import datetime
import traceback
from typing import Any, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP request metrics."""

    def __init__(self, app: Any, metrics_instance: Any, error_reporting: bool = False) -> None:
        super().__init__(app)
        self.metrics = metrics_instance
        # If you want to track errors separately
        # Setting this to true will actually `raise` exceptions after logging them
        self.error_reporting = error_reporting

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track request metrics."""
        start_time = time.perf_counter()

        # Track active requests
        self.metrics._active_requests += 1

        try:
            response = await call_next(request)
            status_code = response.status_code
            # Calculate latency
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000

            # Store metric
            # pylint: disable=protected-access
            await self.metrics._store_http_metric(
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                endpoint=request.url.path,
                method=request.method,
                status_code=status_code,
                latency_ms=latency_ms,
            )
            # pylint: disable=protected-access

            self.metrics._active_requests -= 1
            return response
        except Exception as e:  # pylint: disable=broad-except
            # Track errors
            latency_ms = (time.time() - start_time) * 1000
            # Ensure we have a status_code for final metric storage
            status_code = 500
            # pylint: disable=protected-access
            await self.metrics._store_error(
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                endpoint=request.url.path,
                method=request.method,
                error_type=type(e).__name__,
                error_message=str(e),
                stack_trace=traceback.format_exc(),
                user_agent=request.headers.get("user-agent"),
            )
            # pylint: disable=protected-access
            await self.metrics._store_http_metric(
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                endpoint=request.url.path,
                method=request.method,
                status_code=500,
                latency_ms=latency_ms,
            )
            # pylint: disable=protected-access
            if self.error_reporting:
                # Re-raise so FastAPI's exception handlers take over
                raise
