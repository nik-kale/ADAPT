"""
Health monitoring for ADAPT framework.

Provides health checks for framework components to support monitoring
and alerting in production deployments.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    """
    Result of a health check.

    Attributes:
        component: Name of the component checked
        status: Health status
        message: Human-readable message
        timestamp: When the check was performed
        details: Additional details about the check
        duration_seconds: Time taken to perform check
    """
    component: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'component': self.component,
            'status': self.status.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
            'duration_seconds': self.duration_seconds,
        }


class HealthMonitor:
    """
    Monitor health of ADAPT framework components.

    Performs periodic health checks on connectors, agents, cache,
    and other components.
    """

    def __init__(self):
        """Initialize health monitor"""
        self.last_check_time: Optional[datetime] = None
        self.last_check_results: List[HealthCheck] = []

    async def check_health(self) -> List[HealthCheck]:
        """
        Run all health checks.

        Returns:
            List of health check results
        """
        self.last_check_time = datetime.utcnow()
        checks = []

        # Run all checks in parallel
        check_tasks = [
            self._check_cache(),
            self._check_metrics_collector(),
            self._check_secret_provider(),
        ]

        results = await asyncio.gather(*check_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                checks.append(HealthCheck(
                    component="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {str(result)}"
                ))
            else:
                checks.append(result)

        self.last_check_results = checks
        return checks

    async def _check_cache(self) -> HealthCheck:
        """Check cache health"""
        start_time = datetime.utcnow()

        try:
            from .cache import get_cache

            cache = get_cache()
            stats = await cache.get_stats()

            # Determine status based on cache performance
            if stats['size'] >= stats['max_size'] * 0.9:
                status = HealthStatus.DEGRADED
                message = f"Cache nearly full: {stats['size']}/{stats['max_size']}"
            elif stats['hit_rate'] < 0.5 and stats['total_requests'] > 100:
                status = HealthStatus.DEGRADED
                message = f"Low cache hit rate: {stats['hit_rate']:.2%}"
            else:
                status = HealthStatus.HEALTHY
                message = "Cache operating normally"

            duration = (datetime.utcnow() - start_time).total_seconds()

            return HealthCheck(
                component="cache",
                status=status,
                message=message,
                details=stats,
                duration_seconds=duration
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            return HealthCheck(
                component="cache",
                status=HealthStatus.UNHEALTHY,
                message=f"Cache check failed: {str(e)}",
                duration_seconds=duration
            )

    async def _check_metrics_collector(self) -> HealthCheck:
        """Check metrics collector health"""
        start_time = datetime.utcnow()

        try:
            from .metrics import get_metrics_collector

            collector = get_metrics_collector()
            stats = collector.get_overall_stats()

            # Metrics collector is always healthy if accessible
            status = HealthStatus.HEALTHY
            message = "Metrics collector operational"

            duration = (datetime.utcnow() - start_time).total_seconds()

            return HealthCheck(
                component="metrics_collector",
                status=status,
                message=message,
                details={'stats_available': len(stats) > 0},
                duration_seconds=duration
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            return HealthCheck(
                component="metrics_collector",
                status=HealthStatus.UNHEALTHY,
                message=f"Metrics collector check failed: {str(e)}",
                duration_seconds=duration
            )

    async def _check_secret_provider(self) -> HealthCheck:
        """Check secret provider health"""
        start_time = datetime.utcnow()

        try:
            from .secrets import get_secret_provider

            provider = get_secret_provider()

            # Try to get a test secret (won't exist, but tests connectivity)
            test_result = provider.get_secret("_health_check_test")

            status = HealthStatus.HEALTHY
            message = "Secret provider accessible"

            duration = (datetime.utcnow() - start_time).total_seconds()

            return HealthCheck(
                component="secret_provider",
                status=status,
                message=message,
                details={'provider_type': provider.__class__.__name__},
                duration_seconds=duration
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            return HealthCheck(
                component="secret_provider",
                status=HealthStatus.DEGRADED,
                message=f"Secret provider check failed: {str(e)}",
                duration_seconds=duration
            )

    def get_overall_status(self, checks: Optional[List[HealthCheck]] = None) -> HealthStatus:
        """
        Determine overall health status from individual checks.

        Args:
            checks: List of health checks (uses last results if None)

        Returns:
            Overall health status
        """
        if checks is None:
            checks = self.last_check_results

        if not checks:
            return HealthStatus.UNHEALTHY

        # If any check is unhealthy, overall is unhealthy
        if any(c.status == HealthStatus.UNHEALTHY for c in checks):
            return HealthStatus.UNHEALTHY

        # If any check is degraded, overall is degraded
        if any(c.status == HealthStatus.DEGRADED for c in checks):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get summary of health status.

        Returns:
            Dictionary with health summary
        """
        if not self.last_check_results:
            return {
                'status': 'unknown',
                'message': 'No health checks performed yet',
                'timestamp': datetime.utcnow().isoformat(),
            }

        overall_status = self.get_overall_status()

        return {
            'status': overall_status.value,
            'timestamp': self.last_check_time.isoformat() if self.last_check_time else None,
            'checks': [check.to_dict() for check in self.last_check_results],
            'healthy_count': len([c for c in self.last_check_results if c.status == HealthStatus.HEALTHY]),
            'degraded_count': len([c for c in self.last_check_results if c.status == HealthStatus.DEGRADED]),
            'unhealthy_count': len([c for c in self.last_check_results if c.status == HealthStatus.UNHEALTHY]),
        }


# Global health monitor instance
_health_monitor = HealthMonitor()


def get_health_monitor() -> HealthMonitor:
    """Get the global health monitor instance"""
    return _health_monitor
