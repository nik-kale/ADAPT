"""
ADAPT FastAPI Server

Main API server for the ADAPT RCA platform.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
import logging

from .models import (
    ErrorResponse,
    HealthResponse,
    MetricsResponse,
    RCAResponse,
    RCAStartRequest,
    RCAListItem,
    AgentInfo,
)
from .auth import get_current_user, require_view_incidents, require_run_rca, User
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
    logger.info("Starting ADAPT API v3.0")
    configure_logging(level="INFO", json_format=True)

    yield

    # Shutdown
    logger.info("Shutting down ADAPT API")


# Create FastAPI app
app = FastAPI(
    title="ADAPT RCA Platform API",
    description="AI-powered Root Cause Analysis API",
    version="3.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    from .routes import rca, agents, incidents

    app.include_router(rca.router, prefix="/api/v1", tags=["RCA"])
    app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
    app.include_router(incidents.router, prefix="/api/v1", tags=["Incidents"])
except ImportError as e:
    logger.warning(f"Could not import route modules: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
