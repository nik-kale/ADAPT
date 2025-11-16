"""
Tests for Multi-Tenancy Support
"""

import pytest
from datetime import datetime
from core.tenant import (
    TenantConfig,
    TenantManager,
    TenantAwareOrchestrator,
    get_tenant_context,
    set_tenant_context,
)


@pytest.fixture
def tenant_manager():
    """Create a fresh tenant manager for each test"""
    return TenantManager()


@pytest.fixture
def tenant_config():
    """Sample tenant configuration"""
    return TenantConfig(
        tenant_id="test_tenant",
        name="Test Tenant",
        max_concurrent_rca=5,
        max_storage_gb=50
    )


class TestTenantConfig:
    """Test TenantConfig dataclass"""

    def test_tenant_config_creation(self):
        """Test creating tenant configuration"""
        config = TenantConfig(
            tenant_id="tenant1",
            name="Tenant One",
            max_concurrent_rca=10
        )

        assert config.tenant_id == "tenant1"
        assert config.name == "Tenant One"
        assert config.max_concurrent_rca == 10
        assert config.enabled is True
        assert config.created_at is not None

    def test_tenant_config_with_custom_config(self):
        """Test tenant with custom configuration"""
        config = TenantConfig(
            tenant_id="tenant2",
            name="Tenant Two",
            custom_config={"feature_flags": {"ml_enabled": True}}
        )

        assert config.custom_config["feature_flags"]["ml_enabled"] is True


class TestTenantManager:
    """Test TenantManager"""

    def test_default_tenant_registered(self, tenant_manager):
        """Test that default tenant is registered"""
        default_config = tenant_manager.get_tenant_config("default")
        assert default_config is not None
        assert default_config.tenant_id == "default"

    def test_register_tenant(self, tenant_manager, tenant_config):
        """Test registering a new tenant"""
        tenant_manager.register_tenant(tenant_config)

        config = tenant_manager.get_tenant_config("test_tenant")
        assert config is not None
        assert config.tenant_id == "test_tenant"
        assert config.name == "Test Tenant"

    def test_is_tenant_enabled(self, tenant_manager, tenant_config):
        """Test checking if tenant is enabled"""
        tenant_manager.register_tenant(tenant_config)
        assert tenant_manager.is_tenant_enabled("test_tenant") is True

        # Disable tenant
        config = tenant_manager.get_tenant_config("test_tenant")
        config.enabled = False
        assert tenant_manager.is_tenant_enabled("test_tenant") is False

    def test_check_concurrent_rca_quota(self, tenant_manager, tenant_config):
        """Test concurrent RCA quota checking"""
        tenant_manager.register_tenant(tenant_config)

        # Initially within quota
        assert tenant_manager.check_quota("test_tenant", "concurrent_rca") is True

        # Increment to limit
        for _ in range(5):
            tenant_manager.increment_usage("test_tenant", "active_rcas")

        # Now at limit
        assert tenant_manager.check_quota("test_tenant", "concurrent_rca") is False

    def test_check_storage_quota(self, tenant_manager, tenant_config):
        """Test storage quota checking"""
        tenant_manager.register_tenant(tenant_config)

        # Initially within quota
        assert tenant_manager.check_quota("test_tenant", "storage") is True

        # Increment storage usage
        tenant_manager.increment_usage("test_tenant", "storage_used_gb", 60)

        # Now over quota
        assert tenant_manager.check_quota("test_tenant", "storage") is False

    def test_usage_stats_tracking(self, tenant_manager, tenant_config):
        """Test usage statistics tracking"""
        tenant_manager.register_tenant(tenant_config)

        tenant_manager.increment_usage("test_tenant", "total_rcas", 10)
        tenant_manager.increment_usage("test_tenant", "active_rcas", 3)

        stats = tenant_manager.get_usage_stats("test_tenant")
        assert stats["total_rcas"] == 10
        assert stats["active_rcas"] == 3

        # Decrement
        tenant_manager.decrement_usage("test_tenant", "active_rcas", 2)
        stats = tenant_manager.get_usage_stats("test_tenant")
        assert stats["active_rcas"] == 1


class TestTenantContext:
    """Test tenant context management"""

    def test_set_and_get_tenant_context(self):
        """Test setting and getting tenant context"""
        set_tenant_context("test_tenant")
        assert get_tenant_context() == "test_tenant"

    def test_tenant_context_isolation(self):
        """Test that tenant context is isolated"""
        # This would need async context management to properly test
        # but we can verify the basic functionality
        set_tenant_context("tenant1")
        assert get_tenant_context() == "tenant1"

        set_tenant_context("tenant2")
        assert get_tenant_context() == "tenant2"


@pytest.mark.asyncio
class TestTenantAwareOrchestrator:
    """Test tenant-aware RCA orchestration"""

    @pytest.fixture
    def mock_orchestrator(self):
        """Mock base orchestrator"""
        class MockOrchestrator:
            async def run_rca(self, incident_id, signals, **kwargs):
                # Create a simple mock context
                class MockContext:
                    def __init__(self, incident_id):
                        self.incident_id = incident_id
                        self.metadata = {}

                return MockContext(incident_id)

        return MockOrchestrator()

    async def test_run_rca_with_tenant_isolation(
        self, tenant_manager, tenant_config, mock_orchestrator
    ):
        """Test RCA execution with tenant isolation"""
        tenant_manager.register_tenant(tenant_config)

        tenant_orch = TenantAwareOrchestrator(mock_orchestrator, tenant_manager)

        context = await tenant_orch.run_rca(
            tenant_id="test_tenant",
            incident_id="inc_001",
            signals=[]
        )

        # Verify tenant prefix was added to incident ID
        assert context.incident_id == "test_tenant:inc_001"

    async def test_run_rca_quota_enforcement(
        self, tenant_manager, tenant_config, mock_orchestrator
    ):
        """Test that quotas are enforced"""
        tenant_manager.register_tenant(tenant_config)

        # Max out concurrent RCAs
        tenant_manager.increment_usage("test_tenant", "active_rcas", 5)

        tenant_orch = TenantAwareOrchestrator(mock_orchestrator, tenant_manager)

        # Should raise ValueError due to quota
        with pytest.raises(ValueError, match="exceeded concurrent RCA quota"):
            await tenant_orch.run_rca(
                tenant_id="test_tenant",
                incident_id="inc_002",
                signals=[]
            )

    async def test_run_rca_disabled_tenant(
        self, tenant_manager, tenant_config, mock_orchestrator
    ):
        """Test that disabled tenants cannot run RCA"""
        tenant_config.enabled = False
        tenant_manager.register_tenant(tenant_config)

        tenant_orch = TenantAwareOrchestrator(mock_orchestrator, tenant_manager)

        with pytest.raises(ValueError, match="is disabled"):
            await tenant_orch.run_rca(
                tenant_id="test_tenant",
                incident_id="inc_003",
                signals=[]
            )

    async def test_usage_stats_updated(
        self, tenant_manager, tenant_config, mock_orchestrator
    ):
        """Test that usage statistics are updated after RCA"""
        tenant_manager.register_tenant(tenant_config)

        tenant_orch = TenantAwareOrchestrator(mock_orchestrator, tenant_manager)

        await tenant_orch.run_rca(
            tenant_id="test_tenant",
            incident_id="inc_004",
            signals=[]
        )

        stats = tenant_manager.get_usage_stats("test_tenant")
        assert stats["total_rcas"] == 1
        assert stats["last_rca"] is not None
