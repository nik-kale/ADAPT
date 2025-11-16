"""
Pytest configuration and fixtures for ADAPT tests.

Provides common fixtures and test utilities.
"""

import pytest
from datetime import datetime, timedelta
from typing import List

from core import RCAGraph, ADAPTConfig, OrchestrationContext
from core.signal_normalizer import NormalizedSignal, SignalType
from core.rca_graph import RCANode, NodeType


@pytest.fixture
def sample_config():
    """Sample ADAPT configuration"""
    return ADAPTConfig(
        execution_mode='sequential',
        confidence_threshold=0.7,
        enable_remediation_planning=True
    )


@pytest.fixture
def sample_graph():
    """Sample RCA graph"""
    return RCAGraph(incident_id="test_incident")


@pytest.fixture
def sample_log_signals():
    """Sample log signals for testing"""
    base_time = datetime.utcnow()

    return [
        NormalizedSignal(
            signal_type=SignalType.LOG,
            title="Error log 1",
            description="Connection timeout to database",
            timestamp=base_time,
            source="api-service",
            severity="high",
            metadata={'log_level': 'error'}
        ),
        NormalizedSignal(
            signal_type=SignalType.LOG,
            title="Error log 2",
            description="Connection timeout to database",
            timestamp=base_time + timedelta(seconds=10),
            source="api-service",
            severity="high",
            metadata={'log_level': 'error'}
        ),
        NormalizedSignal(
            signal_type=SignalType.LOG,
            title="Warning log",
            description="High memory usage detected",
            timestamp=base_time + timedelta(seconds=20),
            source="api-service",
            severity="medium",
            metadata={'log_level': 'warning'}
        ),
    ]


@pytest.fixture
def sample_metric_signals():
    """Sample metric signals for testing"""
    base_time = datetime.utcnow()

    return [
        NormalizedSignal(
            signal_type=SignalType.METRIC,
            title="High latency",
            description="http_request_latency_ms = 1500",
            timestamp=base_time,
            source="api-gateway",
            severity="high",
            metadata={'metric_name': 'http_request_latency_ms', 'value': 1500}
        ),
        NormalizedSignal(
            signal_type=SignalType.METRIC,
            title="CPU spike",
            description="cpu_usage_percent = 85",
            timestamp=base_time + timedelta(seconds=10),
            source="api-service",
            severity="medium",
            metadata={'metric_name': 'cpu_usage_percent', 'value': 85}
        ),
    ]


@pytest.fixture
def sample_config_change_signals():
    """Sample configuration change signals"""
    base_time = datetime.utcnow()

    return [
        NormalizedSignal(
            signal_type=SignalType.CONFIG_CHANGE,
            title="Deployment",
            description="Deployed api-service v2.1.0",
            timestamp=base_time - timedelta(minutes=15),
            source="deployment-system",
            severity="medium",
            metadata={
                'component': 'api-service',
                'change_type': 'deployment',
                'before': {'version': 'v2.0.0'},
                'after': {'version': 'v2.1.0'}
            }
        ),
    ]


@pytest.fixture
def sample_orchestration_context(sample_graph, sample_log_signals):
    """Sample orchestration context"""
    return OrchestrationContext(
        incident_id="test_incident",
        graph=sample_graph,
        signals=sample_log_signals
    )


@pytest.fixture
def sample_rca_node():
    """Sample RCA node"""
    return RCANode(
        id="test_symptom_1",
        type=NodeType.SYMPTOM,
        title="High API Latency",
        description="P95 latency increased to 1500ms",
        confidence=0.9,
        metadata={'severity': 'high'}
    )


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state between tests"""
    # Reset cache
    from core.cache import get_cache
    import asyncio

    cache = get_cache()
    asyncio.run(cache.clear())

    # Reset metrics
    from core.metrics import get_metrics_collector
    collector = get_metrics_collector()
    collector.reset()

    yield

    # Cleanup after test
    asyncio.run(cache.clear())
    collector.reset()


# v3.0 Advanced Features Fixtures

@pytest.fixture
def sample_tenant_config():
    """Sample tenant configuration for v3 multi-tenancy tests"""
    from core.tenant import TenantConfig
    return TenantConfig(
        tenant_id="test_tenant",
        name="Test Tenant",
        max_concurrent_rca=10,
        max_storage_gb=100
    )


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for testing"""
    class MockLLMProvider:
        async def complete_with_system(self, system_prompt, user_prompt):
            return {
                'content': 'Mock LLM response',
                'findings': ['Mock finding 1', 'Mock finding 2']
            }
    return MockLLMProvider()


# Skip markers for optional dependencies
def pytest_configure(config):
    """Configure custom pytest markers"""
    config.addinivalue_line(
        "markers", "requires_chromadb: tests requiring chromadb"
    )
    config.addinivalue_line(
        "markers", "requires_ml: tests requiring ML dependencies"
    )
    config.addinivalue_line(
        "markers", "requires_llm: tests requiring LLM API access"
    )
    config.addinivalue_line(
        "markers", "integration: integration tests"
    )
