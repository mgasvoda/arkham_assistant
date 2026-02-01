"""Request/response logging middleware for FastAPI."""

import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core.logging_config import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID for correlation
        request_id = str(uuid.uuid4())[:8]

        # Log request
        start_time = time.perf_counter()
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "extra_data": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "client_host": request.client.host if request.client else None,
                }
            },
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log response
            log_level = "warning" if response.status_code >= 400 else "info"
            getattr(logger, log_level)(
                f"Request completed: {request.method} {request.url.path} -> {response.status_code}",
                extra={
                    "extra_data": {
                        "request_id": request_id,
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                    }
                },
            )

            # Add request ID to response headers for debugging
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "extra_data": {
                        "request_id": request_id,
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                    }
                },
                exc_info=True,
            )
            raise
