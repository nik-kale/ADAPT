"""
Multi-Tenancy Support

Provides tenant isolation and context management for ADAPT.
"""

from contextvars import ContextVar
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Context variable for current tenant
_tenant_context: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)
_user_context: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


@dataclass
class TenantConfig:
    """Configuration for a tenant"""
    tenant_id: str
    name: str
    enabled: bool = True
    max_concurrent_rca: int = 10
    max_storage_gb: int = 100
    allowed_agents: Optional[List[str]] = None
    custom_config: Dict[str, Any] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.custom_config is None:
            self.custom_config = {}


class TenantManager:
    """
    Manages multi-tenancy in ADAPT.

    Features:
    - Tenant registration and configuration
    - Resource quotas per tenant
    - Tenant-specific settings
    - Usage tracking
    """

    def __init__(self):
        self.tenants: Dict[str, TenantConfig] = {}
        self.usage_stats: Dict[str, Dict[str, Any]] = {}

        # Register default tenant
        self.register_tenant(TenantConfig(
            tenant_id="default",
            name="Default Tenant",
            max_concurrent_rca=100,
            max_storage_gb=1000
        ))

    def register_tenant(self, config: TenantConfig) -> None:
        """Register a new tenant"""
        self.tenants[config.tenant_id] = config
        self.usage_stats[config.tenant_id] = {
            'total_rcas': 0,
            'active_rcas': 0,
            'storage_used_gb': 0,
            'last_rca': None
        }
        logger.info(f"Registered tenant: {config.tenant_id}")

    def get_tenant_config(self, tenant_id: str) -> Optional[TenantConfig]:
        """Get tenant configuration"""
        return self.tenants.get(tenant_id)

    def is_tenant_enabled(self, tenant_id: str) -> bool:
        """Check if tenant is enabled"""
        config = self.get_tenant_config(tenant_id)
        return config.enabled if config else False

    def check_quota(self, tenant_id: str, resource: str) -> bool:
        """
        Check if tenant is within quota.

        Args:
            tenant_id: Tenant identifier
            resource: Resource to check (concurrent_rca, storage)

        Returns:
            True if within quota
        """
        config = self.get_tenant_config(tenant_id)
        if not config:
            return False

        usage = self.usage_stats.get(tenant_id, {})

        if resource == 'concurrent_rca':
            return usage.get('active_rcas', 0) < config.max_concurrent_rca
        elif resource == 'storage':
            return usage.get('storage_used_gb', 0) < config.max_storage_gb

        return True

    def increment_usage(self, tenant_id: str, resource: str, amount: int = 1) -> None:
        """Increment resource usage for tenant"""
        if tenant_id not in self.usage_stats:
            self.usage_stats[tenant_id] = {
                'total_rcas': 0,
                'active_rcas': 0,
                'storage_used_gb': 0
            }

        if resource in self.usage_stats[tenant_id]:
            self.usage_stats[tenant_id][resource] += amount

    def decrement_usage(self, tenant_id: str, resource: str, amount: int = 1) -> None:
        """Decrement resource usage for tenant"""
        if tenant_id in self.usage_stats and resource in self.usage_stats[tenant_id]:
            self.usage_stats[tenant_id][resource] = max(0, self.usage_stats[tenant_id][resource] - amount)

    def get_usage_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get usage statistics for tenant"""
        return self.usage_stats.get(tenant_id, {})


# Global tenant manager
_tenant_manager = TenantManager()


def get_tenant_manager() -> TenantManager:
    """Get global tenant manager"""
    return _tenant_manager


def set_tenant_context(tenant_id: str) -> None:
    """Set current tenant context"""
    _tenant_context.set(tenant_id)


def get_tenant_context() -> Optional[str]:
    """Get current tenant context"""
    return _tenant_context.get()


def set_user_context(user_id: str) -> None:
    """Set current user context"""
    _user_context.set(user_id)


def get_user_context() -> Optional[str]:
    """Get current user context"""
    return _user_context.get()


class TenantAwareOrchestrator:
    """
    Tenant-aware RCA orchestrator.

    Enforces tenant isolation and resource quotas.
    """

    def __init__(self, base_orchestrator, tenant_manager: TenantManager):
        self.base_orchestrator = base_orchestrator
        self.tenant_manager = tenant_manager

    async def run_rca(
        self, tenant_id: str, incident_id: str, signals: List[Any], **kwargs
    ):
        """
        Run RCA with tenant isolation.

        Args:
            tenant_id: Tenant identifier
            incident_id: Incident ID
            signals: Normalized signals
            **kwargs: Additional arguments

        Returns:
            OrchestrationContext

        Raises:
            ValueError: If tenant is disabled or over quota
        """
        # Check tenant is enabled
        if not self.tenant_manager.is_tenant_enabled(tenant_id):
            raise ValueError(f"Tenant {tenant_id} is disabled")

        # Check quotas
        if not self.tenant_manager.check_quota(tenant_id, 'concurrent_rca'):
            raise ValueError(f"Tenant {tenant_id} has exceeded concurrent RCA quota")

        # Set tenant context
        token_tenant = _tenant_context.set(tenant_id)

        try:
            # Increment active RCAs
            self.tenant_manager.increment_usage(tenant_id, 'active_rcas')

            # Run RCA with tenant prefix for incident ID
            tenant_incident_id = f"{tenant_id}:{incident_id}"

            context = await self.base_orchestrator.run_rca(
                incident_id=tenant_incident_id,
                signals=signals,
                **kwargs
            )

            # Update usage stats
            self.tenant_manager.increment_usage(tenant_id, 'total_rcas')
            self.tenant_manager.usage_stats[tenant_id]['last_rca'] = datetime.utcnow().isoformat()

            return context

        finally:
            # Decrement active RCAs
            self.tenant_manager.decrement_usage(tenant_id, 'active_rcas')

            # Reset tenant context
            _tenant_context.reset(token_tenant)


class TenantAwareGraphStorage:
    """
    Tenant-aware graph storage wrapper.

    Ensures tenant isolation in graph storage.
    """

    def __init__(self, base_storage):
        self.base_storage = base_storage

    async def save_graph(self, graph, tenant_id: Optional[str] = None) -> str:
        """Save graph with tenant isolation"""
        tenant_id = tenant_id or get_tenant_context() or "default"

        # Add tenant metadata to graph
        graph.metadata['tenant_id'] = tenant_id

        # Prefix incident ID with tenant
        if ':' not in graph.incident_id:
            graph.incident_id = f"{tenant_id}:{graph.incident_id}"

        return await self.base_storage.save_graph(graph)

    async def load_graph(self, graph_id: str, tenant_id: Optional[str] = None):
        """Load graph with tenant isolation"""
        tenant_id = tenant_id or get_tenant_context() or "default"

        # Ensure graph_id has tenant prefix
        if ':' not in graph_id:
            graph_id = f"{tenant_id}:{graph_id}"

        graph = await self.base_storage.load_graph(graph_id)

        # Verify tenant matches
        if graph and graph.metadata.get('tenant_id') != tenant_id:
            logger.warning(f"Tenant mismatch: requested {tenant_id}, got {graph.metadata.get('tenant_id')}")
            return None

        return graph

    async def list_graphs(self, tenant_id: Optional[str] = None, **kwargs):
        """List graphs for a tenant"""
        tenant_id = tenant_id or get_tenant_context() or "default"

        # Get all graphs
        all_graphs = await self.base_storage.list_graphs(**kwargs)

        # Filter by tenant
        tenant_graphs = [
            g for g in all_graphs
            if g.get('incident_id', '').startswith(f"{tenant_id}:")
        ]

        return tenant_graphs


def require_tenant_context():
    """Decorator to require tenant context"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tenant_id = get_tenant_context()
            if not tenant_id:
                raise ValueError("Tenant context required but not set")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
