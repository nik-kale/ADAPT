"""
Security Headers Middleware (v4.0 Security Enhancement)

Adds security headers to all responses to prevent common web vulnerabilities.
"""

import os
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    v4.0 security enhancement to prevent:
    - Cross-site scripting (XSS)
    - Clickjacking
    - MIME type sniffing
    - Content injection
    - Insecure connections

    Headers added:
    - Content-Security-Policy: Prevents XSS and content injection
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Legacy XSS protection
    - Strict-Transport-Security: Enforces HTTPS
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Controls browser features
    """

    def __init__(self, app):
        super().__init__(app)

        # Determine if in production
        self.environment = os.getenv("ENVIRONMENT", "development")

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response"""

        response = await call_next(request)

        # Content Security Policy - Prevents XSS and injection attacks
        # Adjust based on your frontend requirements
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # Adjust based on needs
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",  # Prevent framing
            "base-uri 'self'",
            "form-action 'self'",
        ]

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Legacy XSS protection (modern browsers ignore but good for older ones)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Enforce HTTPS in production
        if self.environment == "production":
            # HSTS: Force HTTPS for 1 year, include subdomains
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (formerly Feature Policy)
        # Disable potentially dangerous features
        permissions_policy_directives = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
            "magnetometer=()",
            "accelerometer=()",
            "gyroscope=()",
        ]

        response.headers["Permissions-Policy"] = ", ".join(
            permissions_policy_directives
        )

        # Remove server header to avoid version disclosure
        if "Server" in response.headers:
            del response.headers["Server"]

        # Remove X-Powered-By if present
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]

        return response
