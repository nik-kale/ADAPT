"""
ADAPT: Agentic Diagnostics & Proactive Troubleshooting Framework

A modular framework for AI-driven root cause analysis.
"""

__version__ = '1.0.0'
__author__ = 'ADAPT Team'

from core import (
    ADAPTConfig,
    RCAGraph,
    RCAOrchestrator,
    load_config,
)

from agents import (
    LogAnalyzerAgent,
    MetricAnalyzerAgent,
    TopologyExplainerAgent,
    ChangeCorrelatorAgent,
    RemediationPlannerAgent,
)

from connectors import (
    SyntheticConnector,
)

__all__ = [
    # Version
    '__version__',
    '__author__',

    # Core
    'ADAPTConfig',
    'RCAGraph',
    'RCAOrchestrator',
    'load_config',

    # Agents
    'LogAnalyzerAgent',
    'MetricAnalyzerAgent',
    'TopologyExplainerAgent',
    'ChangeCorrelatorAgent',
    'RemediationPlannerAgent',

    # Connectors
    'SyntheticConnector',
]
