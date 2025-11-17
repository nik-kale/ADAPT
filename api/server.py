"""
ADAPT FastAPI Server

Main API server for the ADAPT RCA platform.

v4.0: Enhanced with comprehensive security middleware and production-ready defaults
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List
import logging
import os

from .models import (
    ErrorResponse,
    HealthResponse,
    MetricsResponse,
    RCAResponse,
    RCAStartRequest,
    RCAListItem,
    AgentInfo,
)
from .auth import get_current_user, require_view_incidents, require_run_rca, User, get_auth_manager
from .middleware import (
    RateLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    ConcurrencyLimitMiddleware,
    get_rate_limiter,
    get_concurrency_limiter,
)
from core import (
    configure_logging,
    get_health_monitor,
    get_metrics_collector,
    get_graph_storage,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for the API"""
    # Startup
    logger.info("Starting ADAPT API v4.0")
    configure_logging(level="INFO", json_format=True)

    # Start rate limiter cleanup task
    limiter = get_rate_limiter()
    import asyncio
    asyncio.create_task(limiter.start_cleanup())

    # Start auth manager cleanup task (for expired tokens/sessions)
    auth_mgr = get_auth_manager()
    asyncio.create_task(auth_mgr.start_periodic_cleanup())

    yield

    # Shutdown
    logger.info("Shutting down ADAPT API v4.0")


# Create FastAPI app
app = FastAPI(
    title="ADAPT RCA Platform API",
    description="AI-powered Root Cause Analysis API - Production Grade",
    version="4.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# v4.0 Security Enhancement: Secure CORS configuration
# Load allowed origins from environment (whitelist only)
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080"
).split(",")

# Only allow credentials if not using wildcard
ALLOW_CREDENTIALS = "*" not in ALLOWED_ORIGINS

if "*" in ALLOWED_ORIGINS:
    logger.warning(
        "⚠️  SECURITY WARNING: CORS allows all origins (*). "
        "Set ALLOWED_ORIGINS environment variable for production."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # v4.0: Whitelist only
    allow_credentials=ALLOW_CREDENTIALS,  # v4.0: No credentials with wildcard
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],  # v4.0: Explicit methods
    allow_headers=["content-type", "authorization", "x-api-key", "x-request-id"],  # v4.0: Explicit headers
    max_age=3600,  # Cache preflight requests for 1 hour
)

# v4.0 Security Enhancement: Security headers
app.add_middleware(SecurityHeadersMiddleware)

# v4.0 Security Enhancement: Request ID for correlation
app.add_middleware(RequestIDMiddleware)

# v4.0 Security Enhancement: Rate limiting
app.add_middleware(RateLimitMiddleware)

# v4.0 Performance Enhancement: Concurrency limiting (P0 Issue 5.5)
app.add_middleware(ConcurrencyLimitMiddleware)

# v4.0 Security Enhancement: Enforce HTTPS in production
environment = os.getenv("ENVIRONMENT", "development")
if environment == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
    logger.info("HTTPS enforcement enabled (production mode)")

# v4.0 Security Enhancement: Trusted host middleware
# Prevent host header attacks
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
if "*" not in ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
    logger.info(f"Trusted host validation enabled: {ALLOWED_HOSTS}")


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error", detail=str(exc)
        ).model_dump(),
    )


# Health and status endpoints
@app.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint.

    Returns the overall health status of the ADAPT platform.
    """
    monitor = get_health_monitor()
    checks = await monitor.check_health()

    # Determine overall status
    statuses = [c.status.value for c in checks]
    if all(s == "healthy" for s in statuses):
        overall_status = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        components=[
            {
                "component": c.component,
                "status": c.status.value,
                "message": c.message,
                "latency_ms": c.latency_ms,
            }
            for c in checks
        ],
    )


@app.get(
    "/api/v1/metrics",
    response_model=MetricsResponse,
    dependencies=[Depends(require_view_incidents)],
    tags=["System"],
)
async def get_metrics(user: User = Depends(get_current_user)):
    """
    Get platform metrics.

    Returns performance metrics for the ADAPT platform.
    """
    collector = get_metrics_collector()
    stats = collector.get_overall_stats()

    # Extract key metrics
    rca_stats = stats.get("rca_workflow", {})
    agent_stats = stats.get("agents", {})
    findings_stats = stats.get("findings", {})

    return MetricsResponse(
        rca_total=rca_stats.get("total_rcas", 0),
        rca_avg_duration_seconds=rca_stats.get("avg_duration_seconds", 0.0),
        agent_stats=agent_stats,
        findings_stats=findings_stats,
    )


@app.get("/api/v1/version", tags=["System"])
async def get_version():
    """Get API version information"""
    return {
        "version": "3.0.0",
        "api_version": "v1",
        "platform": "ADAPT",
        "description": "Agentic Diagnostics & Proactive Troubleshooting",
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint"""
    return {
        "message": "ADAPT RCA Platform API v3.0",
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }


# Import and include route modules
try:
    from .routes import rca, agents, incidents, tenant, remediation, audit, knowledge, predictions

    app.include_router(rca.router, prefix="/api/v1", tags=["RCA"])
    app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
    app.include_router(incidents.router, prefix="/api/v1", tags=["Incidents"])

    # v3.0 routes
    app.include_router(tenant.router, prefix="/api/v1", tags=["Tenant Management"])
    app.include_router(remediation.router, prefix="/api/v1", tags=["Auto-Remediation"])
    app.include_router(audit.router, prefix="/api/v1", tags=["Audit Logging"])
    app.include_router(knowledge.router, prefix="/api/v1", tags=["Knowledge Base"])
    app.include_router(predictions.router, prefix="/api/v1", tags=["Predictive Detection"])
except ImportError as e:
    logger.warning(f"Could not import route modules: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
