"""Middleware for tracking HTTP request metrics."""
import os
import time
import datetime
import traceback
from typing import Any, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP request metrics."""

    def __init__(
        self, app: Any, metrics_instance: Any, track_errors: bool = False
    ) -> None:
        super().__init__(app)
        self.metrics = metrics_instance
        # If you want to track errors separately
        # Setting this to true will actually `raise` exceptions after logging them
        self.error_reporting = track_errors

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
            latency_ms = (time.perf_counter() - start_time) * 1000
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
            self.metrics._active_requests -= 1
            if self.error_reporting:
                # Re-raise so FastAPI's exception handlers take over
                raise
            # Return 500 response when not re-raising
            # Preventing the application to crash, returning the error as API response
            # use environment variable in STG => DEBUG=true to activate
            from fastapi.responses import JSONResponse
            is_debug = os.getenv("DEBUG", "false").lower() == "true"
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal Server Error",
                    "error": str(e) if is_debug else None,
                    "type": type(e).__name__ if is_debug else None,
                    "traceback": traceback.format_exc() if is_debug else None,
                },
            )
