"""
Integration tests for end-to-end RCA workflows.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from core import RCAOrchestrator, ADAPTConfig
from agents import LogAnalyzerAgent, MetricAnalyzerAgent, ChangeCorrelatorAgent
from connectors import SyntheticConnector, ConnectorConfig


class TestEndToEndRCA:
    """End-to-end integration tests"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_rca_workflow(self):
        """Test complete RCA workflow from signals to root causes"""

        # Setup
        config = ADAPTConfig(execution_mode='sequential')
        orchestrator = RCAOrchestrator(config)

        # Register agents
        orchestrator.register_agent('log_analyzer', LogAnalyzerAgent())
        orchestrator.register_agent('metric_analyzer', MetricAnalyzerAgent())
        orchestrator.register_agent('change_correlator', ChangeCorrelatorAgent())

        # Use synthetic data
        incident_dir = Path("examples/synthetic-incidents/latency-regression")
        if not incident_dir.exists():
            pytest.skip(f"Synthetic incident data not found: {incident_dir}")

        connector = SyntheticConnector(
            ConnectorConfig(connector_type='synthetic'),
            data_dir=str(incident_dir)
        )
        await connector.connect()

        # Fetch signals
        signals = await connector.fetch_all_signals(
            datetime.now() - timedelta(hours=2),
            datetime.now()
        )

        assert len(signals) > 0, "Should have fetched signals"

        # Run RCA
        context = await orchestrator.run_rca(
            incident_id='integration_test',
            signals=signals
        )

        # Verify results
        assert context.end_time is not None
        assert len(context.agent_results) == 3
        assert 'log_analyzer' in context.agent_results
        assert 'metric_analyzer' in context.agent_results
        assert 'change_correlator' in context.agent_results

        # Verify graph was built
        assert len(context.graph.nodes) > 0

        # Cleanup
        await connector.disconnect()

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """Test RCA with parallel agent execution"""

        config = ADAPTConfig(execution_mode='parallel')
        orchestrator = RCAOrchestrator(config)

        orchestrator.register_agent('log_analyzer', LogAnalyzerAgent())
        orchestrator.register_agent('metric_analyzer', MetricAnalyzerAgent())

        # Create minimal test signals
        from core.signal_normalizer import NormalizedSignal, SignalType

        signals = [
            NormalizedSignal(
                signal_type=SignalType.LOG,
                title="Test error",
                description="Test error message",
                timestamp=datetime.utcnow(),
                source="test-service",
                severity="high"
            )
        ]

        context = await orchestrator.run_rca(
            incident_id='parallel_test',
            signals=signals
        )

        # Both agents should have run
        assert 'log_analyzer' in context.agent_results
        assert 'metric_analyzer' in context.agent_results

    @pytest.mark.asyncio
    async def test_adaptive_execution(self):
        """Test RCA with adaptive agent execution"""

        config = ADAPTConfig(execution_mode='adaptive')
        orchestrator = RCAOrchestrator(config)

        orchestrator.register_agent('log_analyzer', LogAnalyzerAgent())
        orchestrator.register_agent('metric_analyzer', MetricAnalyzerAgent())

        from core.signal_normalizer import NormalizedSignal, SignalType

        signals = [
            NormalizedSignal(
                signal_type=SignalType.LOG,
                title="Test",
                description="Test",
                timestamp=datetime.utcnow(),
                source="test",
                severity="high"
            )
        ]

        context = await orchestrator.run_rca(
            incident_id='adaptive_test',
            signals=signals
        )

        # Agents should have run in adaptive mode
        assert len(context.agent_results) > 0
