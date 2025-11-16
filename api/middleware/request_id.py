"""
Request ID Middleware (v4.0 Product Enhancement)

Adds unique request IDs for request correlation and distributed tracing.
"""

import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add unique request IDs to all requests.

    v4.0 enhancement for better observability and debugging.

    Features:
    - Accepts existing X-Request-ID header if provided
    - Generates new UUID if not provided
    - Adds request ID to response headers
    - Stores request ID in request.state for use by handlers
    - Automatically logs request ID with structured logging
    """

    async def dispatch(self, request: Request, call_next):
        """Add request ID to request and response"""

        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID")

        if not request_id:
            # Generate new request ID
            request_id = str(uuid.uuid4())

        # Store in request state for access by handlers
        request.state.request_id = request_id

        # Add to logging context (structured logging)
        extra = {"request_id": request_id, "path": request.url.path}

        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra=extra,
        )

        # Process request
        try:
            response = await call_next(request)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"[status={response.status_code}]",
                extra=extra,
            )

            return response

        except Exception as e:
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"[error={type(e).__name__}: {str(e)}]",
                extra=extra,
                exc_info=True,
            )
            raise


def get_request_id(request: Request) -> str:
    """Helper to get request ID from request state"""
    return getattr(request.state, "request_id", "unknown")
