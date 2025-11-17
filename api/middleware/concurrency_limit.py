"""
Concurrency Limiting Middleware

Prevents resource exhaustion by limiting the number of concurrent requests
to expensive endpoints (e.g., RCA analysis).

v4.0: Critical Performance Issue 5.5
"""

from typing import Callable, Dict, Optional
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class ConcurrencyLimiter:
    """
    Concurrency limiter using semaphores (v4.0).

    Limits the number of concurrent requests per endpoint or globally.
    """

    def __init__(
        self,
        global_limit: int = 100,
        endpoint_limits: Optional[Dict[str, int]] = None
    ):
        """
        Initialize concurrency limiter.

        Args:
            global_limit: Maximum concurrent requests across all endpoints
            endpoint_limits: Per-endpoint limits (e.g., {"/rca/analyze": 10})
        """
        self.global_limit = global_limit
        self.endpoint_limits = endpoint_limits or {}

        # Create semaphores
        self.global_semaphore = asyncio.Semaphore(global_limit)
        self.endpoint_semaphores: Dict[str, asyncio.Semaphore] = {}

        for endpoint, limit in self.endpoint_limits.items():
            self.endpoint_semaphores[endpoint] = asyncio.Semaphore(limit)

        # Stats tracking
        self.stats = {
            'total_requests': 0,
            'concurrent_requests': 0,
            'max_concurrent': 0,
            'rejected_requests': 0,
            'endpoint_stats': {},
        }

        self._lock = asyncio.Lock()

        logger.info(
            f"Initialized concurrency limiter: global={global_limit}, "
            f"endpoints={list(endpoint_limits.keys())}"
        )

    async def acquire(
        self,
        endpoint: str,
        timeout: float = 30.0
    ) -> bool:
        """
        Acquire concurrency slot for endpoint.

        Args:
            endpoint: Endpoint path
            timeout: Timeout in seconds

        Returns:
            True if acquired, False if timeout

        Raises:
            HTTPException: If global or endpoint limit exceeded and timeout
        """
        start_time = time.time()

        # Update stats
        async with self._lock:
            self.stats['total_requests'] += 1
            self.stats['concurrent_requests'] += 1

            if self.stats['concurrent_requests'] > self.stats['max_concurrent']:
                self.stats['max_concurrent'] = self.stats['concurrent_requests']

            if endpoint not in self.stats['endpoint_stats']:
                self.stats['endpoint_stats'][endpoint] = {
                    'total': 0,
                    'concurrent': 0,
                    'rejected': 0,
                }

            self.stats['endpoint_stats'][endpoint]['total'] += 1
            self.stats['endpoint_stats'][endpoint]['concurrent'] += 1

        try:
            # Try to acquire global semaphore
            try:
                acquired_global = await asyncio.wait_for(
                    self.global_semaphore.acquire(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"Global concurrency limit reached ({self.global_limit})"
                )
                async with self._lock:
                    self.stats['rejected_requests'] += 1
                    self.stats['concurrent_requests'] -= 1
                    self.stats['endpoint_stats'][endpoint]['concurrent'] -= 1
                    self.stats['endpoint_stats'][endpoint]['rejected'] += 1

                raise HTTPException(
                    status_code=503,
                    detail=f"Server is at maximum capacity ({self.global_limit} concurrent requests). "
                    "Please try again in a few moments."
                )

            # Try to acquire endpoint-specific semaphore
            if endpoint in self.endpoint_semaphores:
                try:
                    remaining_timeout = timeout - (time.time() - start_time)
                    if remaining_timeout <= 0:
                        raise asyncio.TimeoutError()

                    acquired_endpoint = await asyncio.wait_for(
                        self.endpoint_semaphores[endpoint].acquire(),
                        timeout=remaining_timeout
                    )
                except asyncio.TimeoutError:
                    # Release global semaphore
                    self.global_semaphore.release()

                    logger.warning(
                        f"Endpoint concurrency limit reached for {endpoint} "
                        f"({self.endpoint_limits[endpoint]})"
                    )

                    async with self._lock:
                        self.stats['rejected_requests'] += 1
                        self.stats['concurrent_requests'] -= 1
                        self.stats['endpoint_stats'][endpoint]['concurrent'] -= 1
                        self.stats['endpoint_stats'][endpoint]['rejected'] += 1

                    raise HTTPException(
                        status_code=503,
                        detail=f"Too many concurrent requests to {endpoint} "
                        f"({self.endpoint_limits[endpoint]} max). "
                        "Please wait for other requests to complete."
                    )

            return True

        except Exception:
            # Release any acquired semaphores
            async with self._lock:
                self.stats['concurrent_requests'] -= 1
                self.stats['endpoint_stats'][endpoint]['concurrent'] -= 1
            raise

    async def release(self, endpoint: str):
        """
        Release concurrency slot for endpoint.

        Args:
            endpoint: Endpoint path
        """
        # Release endpoint semaphore
        if endpoint in self.endpoint_semaphores:
            self.endpoint_semaphores[endpoint].release()

        # Release global semaphore
        self.global_semaphore.release()

        # Update stats
        async with self._lock:
            self.stats['concurrent_requests'] -= 1
            if endpoint in self.stats['endpoint_stats']:
                self.stats['endpoint_stats'][endpoint]['concurrent'] -= 1

    async def get_stats(self) -> Dict:
        """Get concurrency stats"""
        async with self._lock:
            return dict(self.stats)


# Global limiter instance
_limiter: Optional[ConcurrencyLimiter] = None


def get_concurrency_limiter() -> ConcurrencyLimiter:
    """Get global concurrency limiter instance"""
    global _limiter

    if _limiter is None:
        # Default limits: 100 global, 10 for RCA endpoints
        _limiter = ConcurrencyLimiter(
            global_limit=100,
            endpoint_limits={
                "/api/rca/analyze": 10,
                "/api/rca/stream": 5,
            }
        )

    return _limiter


class ConcurrencyLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for concurrency limiting (v4.0).

    Applies concurrency limits to configured endpoints.
    """

    def __init__(self, app, limiter: Optional[ConcurrencyLimiter] = None):
        super().__init__(app)
        self.limiter = limiter or get_concurrency_limiter()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with concurrency limiting.

        Args:
            request: The request object
            call_next: Next middleware/handler

        Returns:
            Response from the handler
        """
        # Get endpoint path
        endpoint = request.url.path

        # Check if this endpoint has limits
        needs_limiting = (
            endpoint in self.limiter.endpoint_limits or
            endpoint.startswith("/api/rca/")  # Apply to all RCA endpoints
        )

        if not needs_limiting:
            # No limit for this endpoint
            return await call_next(request)

        # Acquire concurrency slot
        try:
            await self.limiter.acquire(endpoint, timeout=30.0)
        except HTTPException as e:
            # Return 503 Service Unavailable
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "Service Unavailable",
                    "detail": e.detail,
                    "endpoint": endpoint,
                },
                headers={
                    "Retry-After": "10",  # Suggest retry after 10 seconds
                }
            )

        try:
            # Process request
            response = await call_next(request)

            # Add concurrency headers
            stats = await self.limiter.get_stats()
            response.headers["X-Concurrent-Requests"] = str(
                stats['concurrent_requests']
            )
            response.headers["X-Global-Limit"] = str(self.limiter.global_limit)

            if endpoint in self.limiter.endpoint_limits:
                endpoint_limit = self.limiter.endpoint_limits[endpoint]
                endpoint_concurrent = stats['endpoint_stats'].get(endpoint, {}).get(
                    'concurrent', 0
                )
                response.headers["X-Endpoint-Limit"] = str(endpoint_limit)
                response.headers["X-Endpoint-Concurrent"] = str(endpoint_concurrent)

            return response

        finally:
            # Release concurrency slot
            await self.limiter.release(endpoint)
