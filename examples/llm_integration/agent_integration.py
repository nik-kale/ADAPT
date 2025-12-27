"""
LLM-Enhanced Agent Integration Example

Demonstrates using LLM providers within ADAPT agents for root cause analysis.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from core import RCAOrchestrator, ADAPTConfig, OrchestrationContext
from core.rca_graph import RCAGraph
from agents.llm_enhanced_agents import (
    LLMEnhancedLogAnalyzer,
    LLMEnhancedMetricAnalyzer,
    LLMEnhancedChangeCorrelator
)
from agents.llm_providers import AnthropicProvider, set_llm_provider
from connectors import SyntheticConnector, ConnectorConfig


async def run_llm_enhanced_analysis():
    """Run RCA analysis with LLM-enhanced agents"""
    print("=== LLM-Enhanced RCA Analysis ===\n")

    # 1. Initialize LLM provider
    print("1. Initializing LLM provider...")
    llm = AnthropicProvider(model="claude-3-5-sonnet-20241022")
    set_llm_provider(llm)
    print("   ✓ LLM provider ready\n")

    # 2. Load configuration
    print("2. Loading configuration...")
    config = ADAPTConfig(
        execution_mode="sequential",
        llm_enabled=True,
        llm_provider="anthropic",
        log_level="INFO"
    )
    print("   ✓ Configuration loaded\n")

    # 3. Set up data connector
    print("3. Setting up synthetic data connector...")
    connector = SyntheticConnector(
        ConnectorConfig(connector_type='synthetic'),
        data_dir='examples/synthetic-incidents/latency-regression'
    )
    await connector.connect()
    print("   ✓ Connector ready\n")

    # 4. Fetch signals
    print("4. Fetching incident signals...")
    start_time = datetime.now() - timedelta(hours=2)
    end_time = datetime.now()
    signals = await connector.fetch_all_signals(start_time, end_time)
    print(f"   ✓ Fetched {len(signals)} signals\n")

    # 5. Initialize orchestrator with LLM-enhanced agents
    print("5. Initializing orchestrator with LLM-enhanced agents...")
    orchestrator = RCAOrchestrator(config)

    # Register LLM-enhanced agents
    orchestrator.register_agent('log_analyzer', LLMEnhancedLogAnalyzer())
    orchestrator.register_agent('metric_analyzer', LLMEnhancedMetricAnalyzer())
    orchestrator.register_agent('change_correlator', LLMEnhancedChangeCorrelator())

    print("   ✓ Registered 3 LLM-enhanced agents\n")

    # 6. Run RCA analysis
    print("6. Running RCA analysis (this may take 30-60 seconds with LLM)...")
    print("   [LLM is analyzing logs, metrics, and changes...]\n")

    context = await orchestrator.run_rca(
        incident_id="latency-regression-001",
        signals=signals
    )

    # 7. Display results
    print("=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    print()

    # Show agent findings
    print("Agent Findings:")
    print("-" * 60)
    for agent_name, result in context.agent_results.items():
        print(f"\n{agent_name.upper()}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Findings: {len(result.findings)}")
        if result.findings:
            for finding in result.findings[:2]:  # Show first 2
                print(f"    - {finding.title}")

    # Show RCA graph
    print("\n" + "=" * 60)
    print("RCA GRAPH")
    print("=" * 60)
    print(f"  Nodes: {len(context.graph.nodes)}")
    print(f"  Edges: {len(context.graph.edges)}")

    root_causes = context.graph.get_root_causes()
    if root_causes:
        print(f"\n  Root Causes ({len(root_causes)}):")
        for rc in root_causes:
            print(f"    - {rc.title} (confidence: {rc.confidence:.2f})")

    # Show execution metrics
    print("\n" + "=" * 60)
    print("EXECUTION METRICS")
    print("=" * 60)
    print(f"  Total Duration: {context.metadata.get('duration_seconds', 0):.2f}s")
    print(f"  LLM Calls: ~{len(context.agent_results) * 2}")  # Estimate
    print()

    # 8. Cleanup
    await connector.disconnect()
    print("✓ Analysis complete!\n")


async def custom_llm_agent_example():
    """Example of creating a custom LLM-enhanced agent"""
    print("=== Custom LLM Agent Example ===\n")

    from agents.base import BaseAgent, AgentResult
    from agents.llm_providers import get_llm_provider

    class CustomSecurityAnalyzer(BaseAgent):
        """Custom agent that uses LLM for security analysis"""

        async def execute(self, context: OrchestrationContext) -> AgentResult:
            llm = get_llm_provider()

            if llm is None:
                # Fallback to heuristic analysis
                return AgentResult(
                    agent_name=self.name,
                    confidence=0.5,
                    findings=[],
                    metadata={'llm_used': False}
                )

            # Build security-focused prompt
            log_signals = [s for s in context.signals if s.signal_type.value == 'log']
            log_summary = f"Found {len(log_signals)} log entries"

            prompt = f"""Analyze these logs for security concerns:

            {log_summary}

            Look for:
            - Authentication failures
            - Unauthorized access attempts
            - Suspicious patterns

            Provide a brief security assessment."""

            # Get LLM analysis
            response = await llm.complete_with_system(
                system_prompt="You are a cybersecurity expert analyzing system logs.",
                user_prompt=prompt
            )

            return AgentResult(
                agent_name=self.name,
                confidence=0.8,
                findings=[],
                metadata={
                    'llm_used': True,
                    'llm_analysis': response
                }
            )

    # Use the custom agent
    agent = CustomSecurityAnalyzer(name="security_analyzer")
    print(f"Created custom agent: {agent.name}")
    print("This agent uses LLM for security-focused analysis")
    print()


async def main():
    """Run all examples"""
    import os

    # Check for API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("ERROR: Please set ANTHROPIC_API_KEY environment variable")
        print("Example: export ANTHROPIC_API_KEY=sk-ant-xxx")
        return

    # Check if example data exists
    data_dir = Path('examples/synthetic-incidents/latency-regression')
    if not data_dir.exists():
        print(f"WARNING: Example data not found at {data_dir}")
        print("Running custom agent example only...\n")
        await custom_llm_agent_example()
        return

    try:
        await run_llm_enhanced_analysis()
        await custom_llm_agent_example()

    except ImportError as e:
        print(f"ERROR: {e}")
        print("Install dependencies: pip install adapt-framework[llm]")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

