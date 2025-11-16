"""
ADAPT Core Module

This module contains the foundational components for the ADAPT framework:
- RCA Graph model
- Orchestration engine
- Configuration management
- Signal normalization
- Validation and error handling
- Observability and logging
- Metrics collection
- Caching
- Parallel processing
- Secrets management
- Health monitoring
"""

from .rca_graph import RCAGraph, RCANode, RCAEdge, NodeType, EdgeType
from .orchestrator import RCAOrchestrator, OrchestrationContext
from .config import ADAPTConfig, load_config
from .signal_normalizer import SignalNormalizer, NormalizedSignal, SignalType
from .validators import SignalValidator, GraphValidator, ConfigValidator, ValidationError
from .observability import (
    StructuredLogger,
    TracingContext,
    configure_logging,
    get_current_trace_id,
    get_current_span_id,
)
from .metrics import MetricsCollector, get_metrics_collector
from .cache import SimpleCache, get_cache, cached
from .parallel import ParallelProcessor, get_parallel_processor
from .secrets import (
    SecretProvider,
    EnvironmentSecretProvider,
    AWSSecretsManagerProvider,
    HashiCorpVaultProvider,
    ChainedSecretProvider,
    get_secret_provider,
    set_secret_provider,
    get_secret,
)
from .health import HealthMonitor, HealthCheck, HealthStatus, get_health_monitor

__all__ = [
    # RCA Graph
    'RCAGraph',
    'RCANode',
    'RCAEdge',
    'NodeType',
    'EdgeType',

    # Orchestration
    'RCAOrchestrator',
    'OrchestrationContext',

    # Configuration
    'ADAPTConfig',
    'load_config',

    # Signal Processing
    'SignalNormalizer',
    'NormalizedSignal',
    'SignalType',

    # Validation
    'SignalValidator',
    'GraphValidator',
    'ConfigValidator',
    'ValidationError',

    # Observability
    'StructuredLogger',
    'TracingContext',
    'configure_logging',
    'get_current_trace_id',
    'get_current_span_id',

    # Metrics
    'MetricsCollector',
    'get_metrics_collector',

    # Caching
    'SimpleCache',
    'get_cache',
    'cached',

    # Parallel Processing
    'ParallelProcessor',
    'get_parallel_processor',

    # Secrets
    'SecretProvider',
    'EnvironmentSecretProvider',
    'AWSSecretsManagerProvider',
    'HashiCorpVaultProvider',
    'ChainedSecretProvider',
    'get_secret_provider',
    'set_secret_provider',
    'get_secret',

    # Health
    'HealthMonitor',
    'HealthCheck',
    'HealthStatus',
    'get_health_monitor',
]
