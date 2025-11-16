"""
ADAPT Command-Line Interface

Provides a rich CLI for running RCA analyses, managing playbooks,
and interacting with the ADAPT framework.
"""

import click
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import json

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich.markdown import Markdown
from rich import print as rprint

console = Console()


@click.group()
@click.version_option(version='2.0.0')
def cli():
    """
    ADAPT - Agentic Diagnostics & Proactive Troubleshooting

    A modular framework for AI-driven root cause analysis.
    """
    pass


@cli.command()
@click.option('--incident-dir', '-i', required=True, help='Path to incident data directory')
@click.option('--config', '-c', default='config.yaml', help='Configuration file')
@click.option('--output', '-o', default='output', help='Output directory')
@click.option('--format', '-f', type=click.Choice(['json', 'markdown', 'both']), default='both')
@click.option('--playbook', '-p', help='Playbook to use (optional)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def analyze(incident_dir: str, config: str, output: str, format: str, playbook: Optional[str], verbose: bool):
    """Run RCA analysis on incident data"""

    console.print(Panel.fit(
        "[bold blue]ADAPT RCA Analysis[/bold blue]\n"
        f"Incident: {incident_dir}\n"
        f"Config: {config}\n"
        f"Output: {output}",
        title="Starting Analysis"
    ))

    # Run async analysis
    asyncio.run(_run_analysis(incident_dir, config, output, format, playbook, verbose))


async def _run_analysis(
    incident_dir: str,
    config_path: str,
    output_dir: str,
    output_format: str,
    playbook_path: Optional[str],
    verbose: bool
):
    """Internal async analysis runner"""
    from core import load_config, ADAPTConfig, RCAOrchestrator, configure_logging
    from core import get_metrics_collector
    from agents import (
        LogAnalyzerAgent,
        MetricAnalyzerAgent,
        TopologyExplainerAgent,
        ChangeCorrelatorAgent,
        RemediationPlannerAgent
    )
    from connectors import SyntheticConnector, ConnectorConfig

    # Configure logging
    configure_logging(level='DEBUG' if verbose else 'INFO', json_format=False)

    # Load config
    if Path(config_path).exists():
        config = load_config(config_path)
        console.print(f"✓ Loaded configuration from {config_path}")
    else:
        config = ADAPTConfig()
        console.print(f"⚠ Using default configuration ({config_path} not found)")

    # Setup connector
    connector = SyntheticConnector(
        ConnectorConfig(connector_type='synthetic'),
        data_dir=incident_dir
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:

        task = progress.add_task("[cyan]Initializing...", total=100)

        # Connect to data source
        await connector.connect()
        progress.update(task, advance=10, description="[cyan]Connected to data source")

        # Fetch signals
        start_time = datetime.now() - timedelta(hours=2)
        end_time = datetime.now()

        signals = await connector.fetch_all_signals(start_time, end_time)
        progress.update(
            task,
            advance=15,
            description=f"[cyan]Fetched {len(signals)} signals"
        )

        # Initialize orchestrator
        orchestrator = RCAOrchestrator(config)
        progress.update(task, advance=5, description="[cyan]Initializing agents")

        # Register agents
        orchestrator.register_agent('log_analyzer', LogAnalyzerAgent())
        orchestrator.register_agent('metric_analyzer', MetricAnalyzerAgent())
        orchestrator.register_agent('topology_explainer', TopologyExplainerAgent())
        orchestrator.register_agent('change_correlator', ChangeCorrelatorAgent())
        orchestrator.register_agent('remediation_planner', RemediationPlannerAgent())

        progress.update(task, advance=10, description="[cyan]Running RCA analysis")

        # Run RCA
        context = await orchestrator.run_rca(
            incident_id=Path(incident_dir).name,
            signals=signals
        )

        progress.update(task, advance=50, description="[cyan]Analysis complete")

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)

        # Export results
        _export_results(context, output_path, output_format)
        progress.update(task, advance=10, description="[green]Results exported")

    # Display results
    _display_results(context)

    # Display metrics
    metrics_collector = get_metrics_collector()
    _display_metrics(metrics_collector)

    await connector.disconnect()


def _export_results(context, output_path: Path, output_format: str):
    """Export RCA results to files"""

    incident_id = context.incident_id

    if output_format in ['json', 'both']:
        # Export graph as JSON
        graph_file = output_path / f"{incident_id}_graph.json"
        with open(graph_file, 'w') as f:
            f.write(context.graph.to_json())
        console.print(f"✓ Graph exported: {graph_file}")

        # Export full context
        context_file = output_path / f"{incident_id}_context.json"
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
        console.print(f"✓ Context exported: {context_file}")

    if output_format in ['markdown', 'both']:
        # Export narrative
        narrative_file = output_path / f"{incident_id}_narrative.md"
        with open(narrative_file, 'w') as f:
            f.write(context.graph.export_narrative())
        console.print(f"✓ Narrative exported: {narrative_file}")


def _display_results(context):
    """Display RCA results in terminal"""

    # Symptoms
    from core.rca_graph import NodeType

    symptoms = context.graph.get_nodes_by_type(NodeType.SYMPTOM)
    if symptoms:
        console.print("\n[bold]Identified Symptoms:[/bold]")
        for symptom in symptoms:
            console.print(f"  • {symptom.title}")

    # Root causes
    root_causes = context.graph.get_root_causes()
    if root_causes:
        table = Table(title="\n🎯 Root Causes Identified", show_header=True)
        table.add_column("Root Cause", style="cyan", no_wrap=False)
        table.add_column("Confidence", style="magenta", justify="right")
        table.add_column("Agent", style="green")

        for rc in sorted(root_causes, key=lambda x: x.confidence, reverse=True):
            table.add_row(
                rc.title,
                f"{rc.confidence:.1%}",
                rc.metadata.get('agent', 'N/A')
            )

        console.print(table)
    else:
        console.print("\n[yellow]⚠ No root causes identified with high confidence[/yellow]")

    # Agent summary
    console.print("\n[bold]Agent Execution Summary:[/bold]")
    for agent_name, result in context.agent_results.items():
        if isinstance(result, dict):
            findings_count = len(result.get('findings', []))
            icon = "✓" if result.get('success', True) else "✗"
            console.print(f"  {icon} {agent_name}: {findings_count} findings")


def _display_metrics(metrics_collector):
    """Display performance metrics"""

    stats = metrics_collector.get_overall_stats()

    if 'rca_workflow' in stats and stats['rca_workflow']:
        workflow_stats = stats['rca_workflow']
        console.print(f"\n[bold]Performance:[/bold]")
        console.print(f"  Total Duration: {workflow_stats['avg_duration_seconds']:.2f}s")


@cli.command()
@click.option('--name', '-n', required=True, help='Playbook name')
@click.option('--category', '-c', required=True, help='Incident category')
@click.option('--output', '-o', default='playbooks', help='Output directory')
def create_playbook(name: str, category: str, output: str):
    """Create a new playbook template"""

    playbook_template = f"""name: "{name}"
description: "Playbook for {category} incidents"
version: "1.0"
category: "{category}"

metadata:
  severity: "high"
  expected_duration: "30-60 minutes"
  author: "Your Name"
  last_updated: "{datetime.now().date().isoformat()}"

triggers:
  - type: "metric_threshold"
    metric: "your_metric_name"
    condition: "> threshold"
    duration: "5 minutes"

agent_configuration:
  execution_mode: "adaptive"
  agents:
    - name: "log_analyzer"
      enabled: true
      priority: 1

    - name: "metric_analyzer"
      enabled: true
      priority: 1

    - name: "change_correlator"
      enabled: true
      priority: 2

common_root_causes:
  - cause: "Example root cause"
    probability: 0.5
    indicators:
      - "Indicator 1"
      - "Indicator 2"

investigation_steps:
  - step: 1
    action: "First investigation step"
    commands:
      - "Command to run"

remediation_strategies:
  - strategy: "Quick fix"
    actions:
      - "Action to take"
    risk: "low"

tags:
  - "{category}"
"""

    output_path = Path(output)
    output_path.mkdir(exist_ok=True, parents=True)

    filename = output_path / f"{name.lower().replace(' ', '-')}.yaml"
    filename.write_text(playbook_template)

    console.print(f"[green]✓[/green] Created playbook: {filename}")


@cli.command()
def list_agents():
    """List all available agents"""

    table = Table(title="Available Diagnostic Agents", show_header=True)
    table.add_column("Agent", style="cyan", no_wrap=True)
    table.add_column("Description", style="white", no_wrap=False)
    table.add_column("Purpose", style="green", no_wrap=False)

    agents = [
        (
            "log_analyzer",
            "Analyzes log patterns and errors",
            "Error detection, pattern matching, temporal correlation"
        ),
        (
            "metric_analyzer",
            "Detects metric anomalies and trends",
            "Statistical anomaly detection, threshold breaches, trend analysis"
        ),
        (
            "topology_explainer",
            "Maps service dependencies",
            "Dependency mapping, failure propagation, SPOF detection"
        ),
        (
            "change_correlator",
            "Correlates changes with incidents",
            "Deployment correlation, change clustering, rollback detection"
        ),
        (
            "remediation_planner",
            "Generates remediation plans",
            "Risk-assessed action plans, validation steps"
        ),
    ]

    for name, desc, purpose in agents:
        table.add_row(name, desc, purpose)

    console.print(table)


@cli.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json']), default='table')
def health(format: str):
    """Check framework health status"""

    async def _check_health():
        from core import get_health_monitor

        monitor = get_health_monitor()
        checks = await monitor.check_health()
        summary = monitor.get_health_summary()

        if format == 'json':
            rprint(json.dumps(summary, indent=2))
        else:
            # Display as table
            status = summary['status']
            status_color = {
                'healthy': 'green',
                'degraded': 'yellow',
                'unhealthy': 'red'
            }.get(status, 'white')

            console.print(f"\n[bold]Overall Status:[/bold] [{status_color}]{status.upper()}[/{status_color}]")

            table = Table(title="Component Health Checks", show_header=True)
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="white")
            table.add_column("Message", style="white", no_wrap=False)

            for check in summary['checks']:
                status_icon = {
                    'healthy': '[green]✓[/green]',
                    'degraded': '[yellow]⚠[/yellow]',
                    'unhealthy': '[red]✗[/red]'
                }.get(check['status'], '?')

                table.add_row(
                    check['component'],
                    status_icon,
                    check['message']
                )

            console.print(table)

    asyncio.run(_check_health())


@cli.command()
def metrics():
    """Display framework metrics"""

    from core import get_metrics_collector

    collector = get_metrics_collector()
    stats = collector.get_overall_stats()

    console.print("\n[bold]ADAPT Framework Metrics[/bold]\n")

    # RCA Workflow stats
    if 'rca_workflow' in stats and stats['rca_workflow']:
        workflow = stats['rca_workflow']
        table = Table(title="RCA Workflow Statistics", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total RCAs", str(workflow['total_rcas']))
        table.add_row("Avg Duration", f"{workflow['avg_duration_seconds']:.2f}s")
        table.add_row("P95 Duration", f"{workflow['p95_duration_seconds']:.2f}s")

        console.print(table)

    # Agent stats
    if 'agents' in stats and stats['agents']:
        table = Table(title="\nAgent Performance", show_header=True)
        table.add_column("Agent", style="cyan")
        table.add_column("Executions", style="white")
        table.add_column("Success Rate", style="green")
        table.add_column("Avg Duration", style="magenta")

        for agent_name, agent_stats in stats['agents'].items():
            table.add_row(
                agent_name,
                str(agent_stats['total_executions']),
                f"{agent_stats['success_rate']:.1%}",
                f"{agent_stats['avg_duration_seconds']:.2f}s"
            )

        console.print(table)

    # Findings stats
    if 'findings' in stats and stats['findings']:
        findings = stats['findings']
        console.print(f"\n[bold]Findings:[/bold]")
        console.print(f"  Total: {findings['total_findings']}")
        console.print(f"  High Confidence: {findings['high_confidence_count']}")
        console.print(f"  Avg Confidence: {findings['avg_confidence']:.2%}")


@cli.command()
def version():
    """Show version information"""

    version_info = """
    🚀 ADAPT Framework v2.0

    Agentic Diagnostics & Proactive Troubleshooting

    Features:
    • Multi-agent RCA orchestration
    • Graph-based causal modeling
    • LLM-powered analysis
    • Production-grade infrastructure
    • Real-time streaming support
    """

    console.print(Panel(version_info.strip(), title="Version Information", border_style="blue"))


if __name__ == '__main__':
    cli()
