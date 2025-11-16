"""
ADAPT Framework - End-to-End RCA Demonstration

This notebook demonstrates how to use the ADAPT framework to perform
root cause analysis on a synthetic incident.

Prerequisites:
    pip install -r requirements.txt

Usage:
    python notebooks/demo_end_to_end_rca.py
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

# Import ADAPT components
from core import (
    ADAPTConfig,
    RCAOrchestrator,
    OrchestrationContext,
    load_config,
)
from agents import (
    LogAnalyzerAgent,
    MetricAnalyzerAgent,
    TopologyExplainerAgent,
    ChangeCorrelatorAgent,
    RemediationPlannerAgent,
)
from connectors import SyntheticConnector, ConnectorConfig
from core.signal_normalizer import SignalType


async def main():
    """Main demonstration flow"""

    print("=" * 80)
    print("ADAPT Framework - End-to-End RCA Demonstration")
    print("=" * 80)
    print()

    # Step 1: Load configuration
    print("Step 1: Loading ADAPT configuration...")
    config = ADAPTConfig(
        execution_mode='adaptive',
        confidence_threshold=0.7,
        enable_remediation_planning=True,
    )
    print(f"✓ Configuration loaded: {config.execution_mode} mode")
    print()

    # Step 2: Initialize connector for synthetic data
    print("Step 2: Initializing synthetic data connector...")
    incident_dir = Path("examples/synthetic-incidents/latency-regression")
    connector_config = ConnectorConfig(
        connector_type='synthetic',
        endpoint=str(incident_dir),
    )
    connector = SyntheticConnector(connector_config, data_dir=incident_dir)
    await connector.connect()
    print(f"✓ Connected to synthetic incident data: {incident_dir.name}")
    print()

    # Step 3: Fetch signals for the incident
    print("Step 3: Fetching incident signals...")
    start_time = datetime(2025, 1, 15, 13, 0, 0)
    end_time = datetime(2025, 1, 15, 15, 0, 0)

    signals = await connector.fetch_all_signals(start_time, end_time)
    print(f"✓ Fetched {len(signals)} signals:")
    print(f"  - Logs: {len([s for s in signals if s.signal_type == SignalType.LOG])}")
    print(f"  - Metrics: {len([s for s in signals if s.signal_type == SignalType.METRIC])}")
    print(f"  - Config Changes: {len([s for s in signals if s.signal_type == SignalType.CONFIG_CHANGE])}")
    print()

    # Step 4: Initialize RCA orchestrator
    print("Step 4: Initializing RCA orchestrator and agents...")
    orchestrator = RCAOrchestrator(config)

    # Register diagnostic agents
    orchestrator.register_agent('log_analyzer', LogAnalyzerAgent())
    orchestrator.register_agent('metric_analyzer', MetricAnalyzerAgent())
    orchestrator.register_agent('topology_explainer', TopologyExplainerAgent())
    orchestrator.register_agent('change_correlator', ChangeCorrelatorAgent())
    orchestrator.register_agent('remediation_planner', RemediationPlannerAgent())

    print(f"✓ Registered {len(orchestrator.agents)} diagnostic agents")
    print()

    # Step 5: Run RCA analysis
    print("Step 5: Running RCA analysis...")
    print("-" * 80)
    incident_id = "latency_regression_001"

    context = await orchestrator.run_rca(
        incident_id=incident_id,
        signals=signals,
    )

    print(f"✓ RCA analysis completed in {(context.end_time - context.start_time).total_seconds():.2f} seconds")
    print()

    # Step 6: Display results
    print("=" * 80)
    print("RCA ANALYSIS RESULTS")
    print("=" * 80)
    print()

    # Symptoms
    print("IDENTIFIED SYMPTOMS:")
    print("-" * 80)
    symptoms = context.graph.get_nodes_by_type(
        __import__('core.rca_graph', fromlist=['NodeType']).NodeType.SYMPTOM
    )
    for symptom in symptoms:
        print(f"• {symptom.title}")
        print(f"  {symptom.description}")
        print(f"  Severity: {symptom.metadata.get('severity', 'N/A')}")
        print()

    # Agent Results Summary
    print("AGENT ANALYSIS RESULTS:")
    print("-" * 80)
    for agent_name, result in context.agent_results.items():
        print(f"\n{agent_name.upper()}:")
        if isinstance(result, dict):
            findings = result.get('findings', [])
            print(f"  Findings: {len(findings)}")
            for finding in findings[:3]:  # Show top 3 findings
                if isinstance(finding, dict):
                    print(f"  • {finding.get('title', 'Untitled')}")
                    print(f"    Confidence: {finding.get('confidence', 0):.2f}")

    print()

    # Root Causes
    print("ROOT CAUSES IDENTIFIED:")
    print("-" * 80)
    root_causes = context.graph.get_root_causes()
    if root_causes:
        for rc in sorted(root_causes, key=lambda x: x.confidence, reverse=True):
            print(f"• {rc.title}")
            print(f"  {rc.description}")
            print(f"  Confidence: {rc.confidence:.2%}")
            print(f"  Agent: {rc.metadata.get('agent', 'N/A')}")
            print()
    else:
        print("No root causes identified with high confidence.")
        print()

    # Remediation Plan
    if 'remediation_planner' in context.agent_results:
        print("REMEDIATION PLAN:")
        print("-" * 80)
        rem_result = context.agent_results['remediation_planner']
        if isinstance(rem_result, dict):
            rem_plan = rem_result.get('metadata', {}).get('remediation_plan', {})
            actions = rem_plan.get('actions', [])

            if actions:
                print(f"Total Actions: {len(actions)}")
                print(f"Estimated Time: {rem_plan.get('total_estimated_time', 'N/A')}")
                print(f"Overall Risk: {rem_plan.get('risk_assessment', {}).get('overall_risk', 'N/A').upper()}")
                print()

                for action in actions[:5]:  # Show top 5 actions
                    print(f"{action.get('priority', '?')}. {action.get('title', 'Untitled')}")
                    print(f"   {action.get('description', '')}")
                    print(f"   Risk: {action.get('risk', 'N/A')} | ETA: {action.get('estimated_time', 'N/A')}")
                    print()

    # Step 7: Export results
    print("=" * 80)
    print("Step 7: Exporting results...")
    print("-" * 80)

    # Export as JSON
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    graph_file = output_dir / f"{incident_id}_graph.json"
    with open(graph_file, 'w') as f:
        f.write(context.graph.to_json())
    print(f"✓ RCA graph exported to: {graph_file}")

    # Export narrative
    narrative_file = output_dir / f"{incident_id}_narrative.md"
    with open(narrative_file, 'w') as f:
        f.write(context.graph.export_narrative())
    print(f"✓ RCA narrative exported to: {narrative_file}")

    # Export full context
    context_file = output_dir / f"{incident_id}_context.json"
    with open(context_file, 'w') as f:
        context_data = {
            'incident_id': context.incident_id,
            'start_time': context.start_time.isoformat(),
            'end_time': context.end_time.isoformat() if context.end_time else None,
            'total_signals': len(context.signals),
            'agent_results': {
                name: result.to_dict() if hasattr(result, 'to_dict') else result
                for name, result in context.agent_results.items()
            },
            'graph': context.graph.to_dict(),
        }
        json.dump(context_data, f, indent=2)
    print(f"✓ Full context exported to: {context_file}")

    print()
    print("=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Review the exported files in the output/ directory")
    print("2. Examine the RCA graph structure")
    print("3. Try modifying the synthetic incident data")
    print("4. Experiment with different agent configurations")
    print()

    await connector.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
