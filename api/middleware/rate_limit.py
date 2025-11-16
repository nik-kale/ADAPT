"""
Rate Limiting Middleware (v4.0 Security Enhancement)

Implements per-user and per-IP rate limiting to prevent abuse and DoS attacks.
"""

import time
import logging
from typing import Dict, Tuple, Optional
from collections import defaultdict
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        cleanup_interval: int = 300,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # Store: key -> (minute_count, minute_reset, hour_count, hour_reset)
        self.limits: Dict[str, Tuple[int, float, int, float]] = defaultdict(
            lambda: (0, 0.0, 0, 0.0)
        )

        # Start cleanup task
        self.cleanup_interval = cleanup_interval
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup(self):
        """Start periodic cleanup of expired entries"""
        while True:
            await asyncio.sleep(self.cleanup_interval)
            await self.cleanup()

    async def cleanup(self):
        """Remove expired rate limit entries"""
        now = time.time()
        expired_keys = []

        for key, (_, minute_reset, _, hour_reset) in self.limits.items():
            if now > hour_reset + 3600:  # Expired more than an hour ago
                expired_keys.append(key)

        for key in expired_keys:
            del self.limits[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} rate limit entries")

    async def check_rate_limit(self, key: str) -> Tuple[bool, Dict[str, any]]:
        """
        Check if request is within rate limit.

        Args:
            key: Unique identifier (user ID, IP address, API key)

        Returns:
            (allowed, headers) tuple where:
                - allowed: True if request should be allowed
                - headers: Rate limit headers to include in response
        """
        now = time.time()
        minute_count, minute_reset, hour_count, hour_reset = self.limits[key]

        # Check minute window
        if now > minute_reset:
            # Reset minute counter
            minute_count = 0
            minute_reset = now + 60

        # Check hour window
        if now > hour_reset:
            # Reset hour counter
            hour_count = 0
            hour_reset = now + 3600

        # Increment counters
        minute_count += 1
        hour_count += 1

        # Update stored limits
        self.limits[key] = (minute_count, minute_reset, hour_count, hour_reset)

        # Check limits
        allowed = (
            minute_count <= self.requests_per_minute
            and hour_count <= self.requests_per_hour
        )

        # Prepare headers
        headers = {
            "X-RateLimit-Limit-Minute": str(self.requests_per_minute),
            "X-RateLimit-Limit-Hour": str(self.requests_per_hour),
            "X-RateLimit-Remaining-Minute": str(
                max(0, self.requests_per_minute - minute_count)
            ),
            "X-RateLimit-Remaining-Hour": str(
                max(0, self.requests_per_hour - hour_count)
            ),
            "X-RateLimit-Reset-Minute": str(int(minute_reset)),
            "X-RateLimit-Reset-Hour": str(int(hour_reset)),
        }

        if not allowed:
            # Add Retry-After header
            retry_after = int(minute_reset - now)
            headers["Retry-After"] = str(retry_after)

        return allowed, headers


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            requests_per_minute=100,  # 100 requests per minute
            requests_per_hour=5000,  # 5000 requests per hour
        )
    return _rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limiting on API endpoints.

    v4.0 security enhancement to prevent DoS attacks.
    """

    def __init__(self, app, limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        self.limiter = limiter or get_rate_limiter()

        # Exempt health check endpoints from rate limiting
        self.exempt_paths = [
            "/api/v1/health",
            "/api/docs",
            "/api/redoc",
            "/api/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting to requests"""

        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Determine rate limit key (prefer user ID, fallback to IP)
        rate_limit_key = self._get_rate_limit_key(request)

        # Check rate limit
        allowed, headers = await self.limiter.check_rate_limit(rate_limit_key)

        if not allowed:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded for {rate_limit_key} on {request.url.path}"
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "detail": "Too many requests. Please try again later.",
                },
                headers=headers,
            )

        # Proceed with request
        response = await call_next(request)

        # Add rate limit headers to response
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value

        return response

    def _get_rate_limit_key(self, request: Request) -> str:
        """
        Get rate limit key from request.

        Priority: User ID > API Key > IP Address
        """
        # Try to get user from request state (set by auth middleware)
        if hasattr(request.state, "user") and request.state.user:
            user = request.state.user
            return f"user:{user.username}:{user.tenant_id}"

        # Try API key from header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Use hash of API key (don't store full key)
            import hashlib

            key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
            return f"apikey:{key_hash}"

        # Fallback to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
