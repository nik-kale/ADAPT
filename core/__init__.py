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
- Graph database storage
- Real-time streaming support
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
from .graph_storage import GraphStorage, Neo4jGraphStorage, get_graph_storage, set_graph_storage
from .streaming import StreamingOrchestrator, StreamingUpdate, UpdateType

# v3.0 Advanced Features
from .tenant import (
    TenantConfig,
    TenantManager,
    TenantAwareOrchestrator,
    TenantAwareGraphStorage,
    get_tenant_context,
    set_tenant_context,
    get_user_context,
    set_user_context,
)
from .audit import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditLevel,
    get_audit_logger,
)
from .pii_scrubber import (
    PIIScrubber,
    PIIPattern,
    get_pii_scrubber,
)
from .knowledge_base import (
    KnowledgeBase,
    KnowledgeEntry,
    RAGEnhancedOrchestrator,
)
from .auto_remediation import (
    AutoRemediationEngine,
    RemediationPlan,
    RemediationAction,
    RemediationStatus,
    RemediationResult,
    ActionRisk,
    get_remediation_engine,
)
from .predictive_detection import (
    PredictiveDetector,
    IncidentPrediction,
    PredictionSeverity,
    PredictiveMonitor,
)
from .telemetry import (
    setup_telemetry,
    InstrumentedOrchestrator,
    get_tracer,
    get_meter,
)
from .logging_manager import (
    LoggingManager,
    ProgressTracker,
    get_logging_manager,
    get_logger,
    LogLevel,
from .event_grouping import (
    EventGrouper,
    EventGroup,
    GroupingStrategy,
    group_events_by_time_window,
)

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

    # Graph Storage
    'GraphStorage',
    'Neo4jGraphStorage',
    'get_graph_storage',
    'set_graph_storage',

    # Streaming
    'StreamingOrchestrator',
    'StreamingUpdate',
    'UpdateType',

    # v3.0 - Multi-Tenancy
    'TenantConfig',
    'TenantManager',
    'TenantAwareOrchestrator',
    'TenantAwareGraphStorage',
    'get_tenant_context',
    'set_tenant_context',
    'get_user_context',
    'set_user_context',

    # v3.0 - Audit Logging
    'AuditLogger',
    'AuditEvent',
    'AuditEventType',
    'AuditLevel',
    'get_audit_logger',

    # v3.0 - PII Scrubbing
    'PIIScrubber',
    'PIIPattern',
    'get_pii_scrubber',

    # v3.0 - Knowledge Base
    'KnowledgeBase',
    'KnowledgeEntry',
    'RAGEnhancedOrchestrator',

    # v3.0 - Auto-Remediation
    'AutoRemediationEngine',
    'RemediationPlan',
    'RemediationAction',
    'RemediationStatus',
    'RemediationResult',
    'ActionRisk',
    'get_remediation_engine',

    # v3.0 - Predictive Detection
    'PredictiveDetector',
    'IncidentPrediction',
    'PredictionSeverity',
    'PredictiveMonitor',

    # v3.0 - Telemetry
    'setup_telemetry',
    'InstrumentedOrchestrator',
    'get_tracer',
    'get_meter',
    
    # v5.1 - Enhanced Logging
    'LoggingManager',
    'ProgressTracker',
    'get_logging_manager',
    'get_logger',
    'LogLevel',
    # v5.1 - Event Grouping
    'EventGrouper',
    'EventGroup',
    'GroupingStrategy',
    'group_events_by_time_window',
]
