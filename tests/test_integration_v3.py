"""
Integration Tests for v3.0 Features

Tests complete workflows with all v3 features enabled.
"""

import pytest
from datetime import datetime
from core import ADAPTConfig, RCAOrchestrator
from core.signal_normalizer import NormalizedSignal, SignalType
from core.tenant import TenantManager, TenantConfig
from core.pii_scrubber import PIIScrubber


@pytest.mark.integration
@pytest.mark.asyncio
class TestV3Integration:
    """Integration tests for v3 features"""

    @pytest.fixture
    def v3_config(self):
        """Configuration with all v3 features enabled"""
        return ADAPTConfig(
            execution_mode='adaptive',
            # Enable all v3 features
            multi_tenancy_enabled=True,
            audit_enabled=True,
            pii_scrubbing_enabled=True,
        )

    @pytest.fixture
    def tenant_manager(self):
        """Tenant manager with test tenant"""
        manager = TenantManager()
        manager.register_tenant(TenantConfig(
            tenant_id="test_tenant",
            name="Test Tenant",
            max_concurrent_rca=10,
            max_storage_gb=100
        ))
        return manager

    @pytest.fixture
    def sample_signals_with_pii(self):
        """Signals containing PII for testing scrubbing"""
        return [
            NormalizedSignal(
                signal_type=SignalType.LOG,
                title="User Error",
                description="User john.doe@example.com encountered error from IP 192.168.1.100",
                timestamp=datetime.utcnow(),
                source="api-service",
                severity="high",
                metadata={'user': 'john.doe@example.com'}
            ),
            NormalizedSignal(
                signal_type=SignalType.METRIC,
                title="High Error Rate",
                description="Error rate at 15%",
                timestamp=datetime.utcnow(),
                source="monitoring",
                severity="high",
                metadata={'error_rate': 0.15}
            )
        ]

    async def test_orchestrator_with_audit_logging(self, v3_config, sample_signals_with_pii):
        """Test RCA orchestrator with audit logging enabled"""
        orchestrator = RCAOrchestrator(v3_config)

        # Run RCA
        context = await orchestrator.run_rca(
            incident_id="test_inc_001",
            signals=sample_signals_with_pii
        )

        # Verify RCA completed
        assert context.incident_id == "test_inc_001"
        assert context.end_time is not None

        # Note: Full audit verification would require checking storage
        # This test verifies no exceptions were raised

    async def test_orchestrator_with_pii_scrubbing(self, v3_config, sample_signals_with_pii):
        """Test PII scrubbing in orchestrator"""
        orchestrator = RCAOrchestrator(v3_config)

        # Run RCA
        context = await orchestrator.run_rca(
            incident_id="test_inc_002",
            signals=sample_signals_with_pii
        )

        # Verify signals were scrubbed
        for signal in context.signals:
            # Email should be redacted
            assert "john.doe@example.com" not in signal.description
            # IP should be redacted
            assert "192.168.1.100" not in signal.description

    async def test_pii_scrubber_comprehensive(self):
        """Test comprehensive PII scrubbing"""
        scrubber = PIIScrubber()

        test_text = """
        User: john.doe@example.com
        SSN: 123-45-6789
        Credit Card: 4532-1234-5678-9010
        Phone: (555) 123-4567
        IP: 192.168.1.100
        API Key: sk_live_1234567890abcdefghij
        """

        scrubbed = scrubber.scrub_text(test_text)

        # Verify all PII types are redacted
        assert "john.doe@example.com" not in scrubbed
        assert "123-45-6789" not in scrubbed
        assert "4532-1234-5678-9010" not in scrubbed
        assert "(555) 123-4567" not in scrubbed
        assert "192.168.1.100" not in scrubbed
        assert "sk_live_1234567890abcdefghij" not in scrubbed

        # Verify redaction markers present
        assert "[EMAIL_REDACTED]" in scrubbed
        assert "[SSN_REDACTED]" in scrubbed
        assert "[CREDIT_CARD_REDACTED]" in scrubbed

    async def test_tenant_quota_enforcement(self, tenant_manager):
        """Test tenant quota checking"""
        tenant_id = "test_tenant"

        # Initially within quota
        assert tenant_manager.check_quota(tenant_id, "concurrent_rca") is True

        # Max out quota (max_concurrent_rca = 10)
        for _ in range(10):
            tenant_manager.increment_usage(tenant_id, "active_rcas")

        # Now at limit
        assert tenant_manager.check_quota(tenant_id, "concurrent_rca") is False

        # Decrement and check again
        tenant_manager.decrement_usage(tenant_id, "active_rcas", 5)
        assert tenant_manager.check_quota(tenant_id, "concurrent_rca") is True

    async def test_multi_tenant_isolation(self, tenant_manager):
        """Test that tenants are properly isolated"""
        # Create two tenants
        tenant_manager.register_tenant(TenantConfig(
            tenant_id="tenant_a",
            name="Tenant A",
            max_concurrent_rca=5
        ))
        tenant_manager.register_tenant(TenantConfig(
            tenant_id="tenant_b",
            name="Tenant B",
            max_concurrent_rca=10
        ))

        # Increment usage for tenant A
        tenant_manager.increment_usage("tenant_a", "total_rcas", 100)
        tenant_manager.increment_usage("tenant_b", "total_rcas", 200)

        # Verify isolation
        stats_a = tenant_manager.get_usage_stats("tenant_a")
        stats_b = tenant_manager.get_usage_stats("tenant_b")

        assert stats_a["total_rcas"] == 100
        assert stats_b["total_rcas"] == 200

    async def test_agent_audit_logging(self, v3_config):
        """Test agent execution with audit logging"""
        from agents.base import BaseAgent, AgentResult

        class TestAgent(BaseAgent):
            async def execute(self, context):
                return AgentResult(
                    agent_name=self.name,
                    findings=[{
                        'id': 'finding_001',
                        'title': 'Test Finding',
                        'description': 'Test',
                        'confidence': 0.9
                    }],
                    success=True
                )

        # Create mock context
        class MockContext:
            incident_id = "test_inc_003"

        agent = TestAgent("test_agent")
        context = MockContext()

        # Execute with audit logging
        result = await agent.execute_with_audit(context)

        # Verify execution succeeded
        assert result.success is True
        assert len(result.findings) == 1

        # Note: Full audit verification would require checking storage


@pytest.mark.integration
@pytest.mark.asyncio
class TestV3APIIntegration:
    """Integration tests for v3 API endpoints"""

    async def test_tenant_lifecycle(self):
        """Test complete tenant management lifecycle"""
        from api.routes.tenant import get_tenant_manager

        manager = get_tenant_manager()

        # Create tenant
        config = TenantConfig(
            tenant_id="api_test_tenant",
            name="API Test Tenant",
            max_concurrent_rca=15
        )
        manager.register_tenant(config)

        # Verify created
        retrieved = manager.get_tenant_config("api_test_tenant")
        assert retrieved is not None
        assert retrieved.name == "API Test Tenant"

        # Update usage
        manager.increment_usage("api_test_tenant", "total_rcas", 50)
        stats = manager.get_usage_stats("api_test_tenant")
        assert stats["total_rcas"] == 50

        # Check quota
        assert manager.check_quota("api_test_tenant", "concurrent_rca") is True

    async def test_knowledge_base_if_available(self):
        """Test knowledge base functionality if dependencies available"""
        try:
            from core.knowledge_base import KnowledgeBase

            kb = KnowledgeBase()
            initialized = await kb.initialize()

            if not initialized:
                pytest.skip("Knowledge base dependencies not available")

            # Test statistics
            stats = await kb.get_statistics()
            assert 'total_entries' in stats

        except ImportError:
            pytest.skip("Knowledge base dependencies not installed")

    async def test_predictive_detector_if_available(self):
        """Test predictive detector if dependencies available"""
        try:
            from core.predictive_detection import PredictiveDetector

            detector = PredictiveDetector()
            initialized = await detector.initialize()

            if not initialized:
                pytest.skip("Predictive detection dependencies not available")

            # Test prediction with empty data
            predictions = await detector.predict_incidents(
                current_metrics=[],
                recent_signals=[]
            )

            # Should return empty list or predictions
            assert isinstance(predictions, list)

        except ImportError:
            pytest.skip("Predictive detection dependencies not installed")


@pytest.mark.integration
@pytest.mark.asyncio
class TestV3EndToEndWorkflow:
    """End-to-end integration tests"""

    async def test_complete_rca_workflow_with_v3_features(self):
        """Test complete RCA workflow with all v3 features"""
        # Configure with v3 features
        config = ADAPTConfig(
            execution_mode='sequential',
            audit_enabled=True,
            pii_scrubbing_enabled=True,
            pii_scrub_signals=True
        )

        # Create orchestrator
        orchestrator = RCAOrchestrator(config)

        # Create signals with PII
        signals = [
            NormalizedSignal(
                signal_type=SignalType.LOG,
                title="Database Error",
                description="Connection failed for user alice@company.com from 10.0.1.50",
                timestamp=datetime.utcnow(),
                source="database",
                severity="high",
                metadata={}
            ),
            NormalizedSignal(
                signal_type=SignalType.METRIC,
                title="High Latency",
                description="Query latency > 5000ms",
                timestamp=datetime.utcnow(),
                source="database",
                severity="medium",
                metadata={'latency_ms': 5500}
            )
        ]

        # Run RCA
        context = await orchestrator.run_rca(
            incident_id="e2e_test_001",
            signals=signals
        )

        # Verify workflow completed
        assert context.incident_id == "e2e_test_001"
        assert context.end_time is not None
        assert len(context.signals) > 0

        # Verify PII was scrubbed from signals
        for signal in context.signals:
            assert "alice@company.com" not in signal.description
            assert "10.0.1.50" not in signal.description

        # Verify RCA graph was created
        assert len(context.graph.nodes) > 0

        # Verify execution metadata exists
        assert context.start_time is not None
        duration = (context.end_time - context.start_time).total_seconds()
        assert duration >= 0

    async def test_workflow_with_tenant_context(self):
        """Test RCA workflow with tenant context"""
        from core.tenant import TenantManager, set_tenant_context

        # Setup tenant
        manager = TenantManager()
        manager.register_tenant(TenantConfig(
            tenant_id="workflow_tenant",
            name="Workflow Tenant"
        ))

        # Set tenant context
        set_tenant_context("workflow_tenant")

        # Configure and run RCA
        config = ADAPTConfig(multi_tenancy_enabled=True)
        orchestrator = RCAOrchestrator(config)

        signals = [
            NormalizedSignal(
                signal_type=SignalType.LOG,
                title="Test Signal",
                description="Test",
                timestamp=datetime.utcnow(),
                source="test",
                severity="low",
                metadata={}
            )
        ]

        context = await orchestrator.run_rca(
            incident_id="tenant_test_001",
            signals=signals
        )

        # Verify completed
        assert context.incident_id == "tenant_test_001"


@pytest.mark.integration
def test_v3_configuration_validation():
    """Test v3 configuration system"""
    # Test default config
    config = ADAPTConfig()

    # Verify v3 defaults
    assert hasattr(config, 'multi_tenancy_enabled')
    assert hasattr(config, 'audit_enabled')
    assert hasattr(config, 'pii_scrubbing_enabled')
    assert hasattr(config, 'auto_remediation_enabled')
    assert hasattr(config, 'knowledge_base_enabled')
    assert hasattr(config, 'predictive_detection_enabled')

    # Test to_dict includes v3 settings
    config_dict = config.to_dict()
    assert 'multi_tenancy_enabled' in config_dict
    assert 'audit_enabled' in config_dict
    assert 'pii_scrubbing_enabled' in config_dict

    # Test enabling all features
    full_config = ADAPTConfig(
        multi_tenancy_enabled=True,
        audit_enabled=True,
        pii_scrubbing_enabled=True,
        auto_remediation_enabled=True,
        knowledge_base_enabled=True,
        predictive_detection_enabled=True,
        llm_enabled=True,
        telemetry_enabled=True
    )

    assert full_config.multi_tenancy_enabled is True
    assert full_config.audit_enabled is True
    assert full_config.pii_scrubbing_enabled is True
