"""
ADAPT Connectors Module

Provides interfaces and implementations for connecting to various
telemetry sources (logs, metrics, traces, config stores).
"""

from .base import BaseConnector, ConnectorConfig
from .synthetic_connector import SyntheticConnector

__all__ = [
    'BaseConnector',
    'ConnectorConfig',
    'SyntheticConnector',
]
