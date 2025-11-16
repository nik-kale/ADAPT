# ADAPT Architecture

## Overview

ADAPT (Agentic Diagnostics & Proactive Troubleshooting) is a modular framework for building AI-driven root cause analysis systems. The architecture emphasizes extensibility, clarity, and production-grade patterns.

## Core Concepts

### 1. RCA Graph Model

At the heart of ADAPT is a directed graph that represents the diagnostic process:

```
Symptoms → Hypotheses → Tests → Findings → Root Causes
     ↑                                           ↓
     └─────────────────────────────────────────┘
                   (causal links)
```

**Node Types:**
- **Symptoms**: Observable issues (high latency, errors, failures)
- **Hypotheses**: Potential causes to investigate
- **Tests**: Diagnostic checks performed
- **Findings**: Confirmed observations from analysis
- **Root Causes**: Identified root causes
- **Contributing Factors**: Secondary factors that exacerbate issues

**Edge Types:**
- **suggests**: Symptom suggests hypothesis
- **requires**: Hypothesis requires test
- **confirms**: Test confirms finding
- **refutes**: Test refutes hypothesis
- **causes**: Root cause causes symptom
- **contributes_to**: Factor contributes to symptom

### 2. Multi-Agent Orchestration

ADAPT uses multiple specialized diagnostic agents that work together:

```
┌─────────────────────────────────────────┐
│     RCA Orchestrator                    │
│  (coordinates diagnostic workflow)      │
└─────────────────┬───────────────────────┘
                  │
      ┌───────────┴───────────┐
      │                       │
      ▼                       ▼
┌──────────┐           ┌──────────┐
│  Logs    │           │ Metrics  │
│ Analyzer │           │ Analyzer │
└──────────┘           └──────────┘
      │                       │
      └───────────┬───────────┘
                  │
      ┌───────────┴───────────────┐
      │                           │
      ▼                           ▼
┌──────────┐               ┌──────────┐
│Topology  │               │ Change   │
│Explainer │               │Correlator│
└──────────┘               └──────────┘
      │                           │
      └───────────┬───────────────┘
                  │
                  ▼
         ┌──────────────┐
         │ Remediation  │
         │   Planner    │
         └──────────────┘
```

**Execution Modes:**
- **Sequential**: Run agents one after another
- **Parallel**: Run independent agents simultaneously
- **Adaptive**: Dynamically determine agent execution order based on intermediate results

### 3. Signal Normalization Layer

All telemetry data is normalized into a unified `NormalizedSignal` format:

```python
{
    "signal_type": "log|metric|trace|config_change|alert",
    "title": "Short description",
    "description": "Detailed information",
    "timestamp": "ISO-8601 timestamp",
    "source": "Service/host identifier",
    "severity": "low|medium|high|critical",
    "metadata": {...},
    "tags": {...}
}
```

This abstraction allows agents to work with data from any source without modification.

### 4. Connector Architecture

Connectors provide a pluggable interface for fetching telemetry data:

```
┌──────────────────┐
│  BaseConnector   │  (abstract interface)
└────────┬─────────┘
         │
    ┌────┴────┬──────────────┬──────────────┐
    │         │              │              │
    ▼         ▼              ▼              ▼
┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐
│Synthetic│ │Prometheus│ │Elasticsearch│ │CloudWatch│
│Connector│ │Connector │ │ Connector  │ │Connector │
└────────┘ └────────┘ └──────────┘ └──────────┘
```

Each connector implements:
- `fetch_logs()`: Retrieve log entries
- `fetch_metrics()`: Retrieve metric data
- `fetch_config_changes()`: Retrieve configuration changes
- `fetch_all_signals()`: Retrieve all available signals

## Data Flow

### End-to-End RCA Workflow

```
1. Signal Ingestion
   ┌──────────────┐
   │ Connectors   │
   │ fetch data   │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │ Normalizer   │
   │ standardizes │
   └──────┬───────┘
          │
          ▼
2. Symptom Identification
   ┌──────────────┐
   │ Orchestrator │
   │ creates RCA  │
   │ graph with   │
   │ symptoms     │
   └──────┬───────┘
          │
          ▼
3. Agent Execution
   ┌──────────────┐
   │ Diagnostic   │
   │ Agents run   │
   │ analysis     │
   └──────┬───────┘
          │
          ▼
4. Findings Synthesis
   ┌──────────────┐
   │ Orchestrator │
   │ aggregates   │
   │ findings     │
   └──────┬───────┘
          │
          ▼
5. Root Cause Identification
   ┌──────────────┐
   │ High-conf.   │
   │ findings →   │
   │ root causes  │
   └──────┬───────┘
          │
          ▼
6. Remediation Planning
   ┌──────────────┐
   │ Remediation  │
   │ Planner      │
   │ generates    │
   │ action plan  │
   └──────┬───────┘
          │
          ▼
7. Output
   ┌──────────────┐
   │ RCA Graph    │
   │ Narrative    │
   │ Action Plan  │
   └──────────────┘
```

## Component Architecture

### Core Module (`core/`)

**RCA Graph** (`rca_graph.py`)
- Graph data structure with nodes and edges
- Methods for traversal and querying
- Export to JSON and narrative formats

**Orchestrator** (`orchestrator.py`)
- Coordinates RCA workflow
- Manages agent execution
- Aggregates results into RCA graph

**Configuration** (`config.py`)
- Loads and validates framework configuration
- Supports YAML and JSON formats
- Manages agent and connector settings

**Signal Normalizer** (`signal_normalizer.py`)
- Converts raw telemetry to normalized format
- Provides adapters for different data types
- Handles batch normalization

### Agents Module (`agents/`)

Each agent inherits from `BaseAgent` and implements:

```python
async def execute(self, context: OrchestrationContext) -> AgentResult:
    """
    Perform diagnostic analysis and return findings.

    Args:
        context: Contains RCA graph, signals, and agent results

    Returns:
        AgentResult with findings, hypotheses, and metadata
    """
```

**Log Analyzer**
- Detects error patterns and spikes
- Identifies temporal patterns
- Correlates errors across services

**Metric Analyzer**
- Detects anomalies using statistical methods
- Identifies threshold breaches
- Analyzes trends and correlations

**Topology Explainer**
- Maps service dependencies
- Analyzes failure propagation
- Identifies single points of failure

**Change Correlator**
- Correlates changes with symptoms
- Detects change clusters
- Identifies rollback opportunities

**Remediation Planner**
- Generates actionable remediation steps
- Assesses risk for each action
- Provides validation procedures

### Connectors Module (`connectors/`)

**Base Connector**
- Abstract interface for all connectors
- Defines standard methods for data fetching
- Handles connection lifecycle

**Synthetic Connector**
- Loads pre-generated incident data
- Generates random synthetic data
- Useful for testing and demonstrations

## Scalability Considerations

### Horizontal Scaling

- **Stateless Design**: Orchestrator is stateless; RCA sessions can run on any node
- **Async/Await**: All I/O operations are asynchronous for concurrency
- **Agent Parallelization**: Independent agents can run on separate workers

### Performance Optimization

- **Lazy Loading**: Load only required data based on playbook
- **Caching**: Cache frequently accessed data (topology, playbooks)
- **Batching**: Batch signal processing where possible
- **Early Exit**: Stop analysis when high-confidence root cause found

### Production Deployment

```
┌─────────────────────────────────────────────┐
│            Load Balancer                    │
└─────────────────┬───────────────────────────┘
                  │
      ┌───────────┴───────────┐
      │                       │
      ▼                       ▼
┌──────────┐           ┌──────────┐
│  ADAPT   │           │  ADAPT   │
│ Instance │           │ Instance │
│    #1    │           │    #2    │
└────┬─────┘           └────┬─────┘
     │                      │
     └──────────┬───────────┘
                │
    ┌───────────┴────────────┐
    │                        │
    ▼                        ▼
┌────────┐            ┌──────────┐
│ Message│            │ Results  │
│ Queue  │            │ Storage  │
│ (Tasks)│            │ (Redis/S3│
└────────┘            └──────────┘
```

## Extension Points

### Adding New Agents

1. Inherit from `BaseAgent`
2. Implement `execute()` method
3. Register with orchestrator
4. Update playbooks to include agent

### Adding New Connectors

1. Inherit from `BaseConnector`
2. Implement required fetch methods
3. Handle connection lifecycle
4. Add connector configuration

### Adding New Signal Types

1. Add to `SignalType` enum
2. Create normalizer method
3. Update connector implementations
4. Teach agents to understand new type

## Security Considerations

- **Credential Management**: Use secrets manager for connector credentials
- **Data Sanitization**: Sanitize sensitive data before analysis
- **RBAC**: Implement role-based access for RCA operations
- **Audit Logging**: Log all RCA operations for compliance
- **Encryption**: Encrypt data in transit and at rest
