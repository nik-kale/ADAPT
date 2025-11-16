# ADAPT: Agentic Diagnostics & Proactive Troubleshooting Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

ADAPT is an open, modular framework for building agentic AI-driven root-cause analysis (RCA) and proactive troubleshooting workflows in modern cloud, SaaS, and security environments. It provides a production-inspired architecture that combines signal adapters, multi-agent orchestration, graph-based RCA modeling, change-correlation logic, and structured remediation planning.

## ✨ Key Features

- **📊 Graph-Based RCA Model**: Represent complex diagnostic processes as directed graphs with symptoms, hypotheses, findings, and root causes
- **🤖 Multi-Agent Architecture**: Specialized diagnostic agents for logs, metrics, topology, changes, and remediation
- **🔄 Flexible Orchestration**: Sequential, parallel, or adaptive agent execution modes
- **🔌 Pluggable Connectors**: Abstract interface for any telemetry source (logs, metrics, traces, config changes)
- **📋 Playbook-Driven Analysis**: YAML-based scenario definitions encode domain knowledge
- **📈 Confidence Scoring**: Probabilistic findings with transparency into certainty levels
- **🛠️ Remediation Planning**: Automated generation of prioritized, risk-assessed action plans
- **💬 UI-Ready Outputs**: Structured JSON for dashboards and narrative Markdown for humans

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    ADAPT Framework                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐      ┌──────────────┐               │
│  │  Connectors  │──────│  Normalizer  │               │
│  │ (Data Sources)│      │   (Signals)  │               │
│  └──────────────┘      └──────┬───────┘               │
│                                │                        │
│                         ┌──────▼────────┐              │
│                         │ Orchestrator  │              │
│                         │   (Workflow)  │              │
│                         └──────┬────────┘              │
│                                │                        │
│         ┌──────────────────────┼──────────┐            │
│         │                      │          │            │
│    ┌────▼────┐  ┌────▼────┐  ┌▼────┐  ┌─▼──────┐     │
│    │  Log    │  │ Metric  │  │Topo │  │ Change │     │
│    │Analyzer │  │Analyzer │  │Expl.│  │Correl. │     │
│    └────┬────┘  └────┬────┘  └┬────┘  └─┬──────┘     │
│         │            │         │         │            │
│         └────────────┴─────────┴─────────┘            │
│                      │                                 │
│              ┌───────▼────────┐                        │
│              │   RCA Graph    │                        │
│              │ (Causal Model) │                        │
│              └───────┬────────┘                        │
│                      │                                 │
│              ┌───────▼────────┐                        │
│              │  Remediation   │                        │
│              │    Planner     │                        │
│              └────────────────┘                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ADAPT.git
cd ADAPT

# Install dependencies
pip install -r requirements.txt

# (Optional) Install in development mode
pip install -e .
```

### Run Your First RCA

```bash
# Run the demonstration notebook
python notebooks/demo_end_to_end_rca.py
```

This will:
1. Load synthetic incident data (API latency regression)
2. Run all diagnostic agents
3. Build an RCA graph
4. Identify root causes
5. Generate a remediation plan
6. Export results to `output/`

### Basic Usage

```python
import asyncio
from datetime import datetime, timedelta
from core import ADAPTConfig, RCAOrchestrator
from agents import (
    LogAnalyzerAgent,
    MetricAnalyzerAgent,
    ChangeCorrelatorAgent,
    RemediationPlannerAgent
)
from connectors import SyntheticConnector, ConnectorConfig

async def analyze_incident():
    # Configure ADAPT
    config = ADAPTConfig(execution_mode='adaptive')

    # Set up data connector
    connector = SyntheticConnector(
        ConnectorConfig(connector_type='synthetic'),
        data_dir='examples/synthetic-incidents/latency-regression'
    )
    await connector.connect()

    # Fetch signals
    signals = await connector.fetch_all_signals(
        start_time=datetime.now() - timedelta(hours=2),
        end_time=datetime.now()
    )

    # Initialize orchestrator and register agents
    orchestrator = RCAOrchestrator(config)
    orchestrator.register_agent('log_analyzer', LogAnalyzerAgent())
    orchestrator.register_agent('metric_analyzer', MetricAnalyzerAgent())
    orchestrator.register_agent('change_correlator', ChangeCorrelatorAgent())
    orchestrator.register_agent('remediation_planner', RemediationPlannerAgent())

    # Run RCA
    context = await orchestrator.run_rca(
        incident_id='inc_001',
        signals=signals
    )

    # Get results
    root_causes = context.graph.get_root_causes()
    for rc in root_causes:
        print(f"Root Cause: {rc.title} (confidence: {rc.confidence:.2%})")

    # Export narrative
    print(context.graph.export_narrative())

    await connector.disconnect()

# Run it
asyncio.run(analyze_incident())
```

## 📁 Repository Structure

```
ADAPT/
├── core/                          # Core framework components
│   ├── rca_graph.py              # Graph model (nodes, edges)
│   ├── orchestrator.py           # Agent orchestration engine
│   ├── config.py                 # Configuration management
│   └── signal_normalizer.py     # Telemetry normalization
│
├── agents/                        # Diagnostic agents
│   ├── base.py                   # Base agent interface
│   ├── log_analyzer.py          # Log analysis agent
│   ├── metric_analyzer.py       # Metric analysis agent
│   ├── topology_explainer.py    # Topology analysis agent
│   ├── change_correlator.py     # Change correlation agent
│   └── remediation_planner.py   # Remediation planning agent
│
├── connectors/                    # Data source connectors
│   ├── base.py                   # Base connector interface
│   └── synthetic_connector.py   # Synthetic data connector
│
├── playbooks/                     # Incident scenario playbooks
│   ├── latency-regression.yaml
│   ├── auth-service-failure.yaml
│   └── network-degradation.yaml
│
├── examples/                      # Example incidents
│   └── synthetic-incidents/
│       ├── latency-regression/
│       │   ├── incident_manifest.json
│       │   ├── logs.json
│       │   ├── metrics.json
│       │   └── config_changes.json
│       └── auth-service-failure/
│           └── ...
│
├── ui-examples/                   # UI integration examples
│   ├── chat-interface/           # Chat-based RCA outputs
│   └── dashboard-widgets/        # Dashboard widget configs
│
├── notebooks/                     # Demonstration notebooks
│   └── demo_end_to_end_rca.py
│
├── docs/                          # Documentation
│   ├── architecture.md           # System architecture
│   ├── design-decisions.md       # Design rationale
│   ├── component-catalog.md      # Component reference
│   └── roadmap.md                # Future plans
│
├── tests/                         # Test suite
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Project metadata
└── README.md                      # This file
```

## 🎯 What Makes ADAPT Different

### 1. Production-Grade Architecture
ADAPT isn't a toy demo—it's built with production patterns:
- Async/await for concurrency
- Type hints and dataclasses
- Modular, extensible design
- Comprehensive error handling

### 2. Graph-Based Causality
Unlike linear diagnostic flows, ADAPT uses a graph to represent:
- Multiple symptoms → multiple root causes
- Causal relationships with confidence scores
- Full traceability from symptom to remediation

### 3. Agent Specialization
Each agent is an expert in its domain:
- **Log Analyzer**: Pattern matching, error rate analysis, temporal correlation
- **Metric Analyzer**: Statistical anomaly detection, trend analysis
- **Topology Explainer**: Dependency mapping, failure propagation
- **Change Correlator**: Deployment correlation, change clustering
- **Remediation Planner**: Risk-assessed action plans

### 4. Playbook-Driven Intelligence
Encode organizational knowledge in playbooks:
- Common root causes with probabilities
- Investigation procedures
- Remediation strategies
- Success criteria

### 5. Designed for Integration
ADAPT outputs are ready for:
- Chat interfaces (Slack, Teams)
- Dashboards (Grafana, Datadog)
- Incident management tools (PagerDuty, Opsgenie)
- Documentation systems (Confluence, Notion)

## 📚 Example Use Cases

### Use Case 1: API Latency Spike
**Symptoms**: P95 latency increased from 200ms to 1500ms

**ADAPT Analysis**:
- Log Analyzer: Detects database timeout errors
- Metric Analyzer: Finds 50x increase in query count
- Change Correlator: Identifies deployment 15 minutes before symptom
- **Root Cause**: N+1 query pattern in recent deployment
- **Remediation**: Rollback deployment, fix query, redeploy

### Use Case 2: Authentication Failures
**Symptoms**: 95% of login attempts failing

**ADAPT Analysis**:
- Log Analyzer: SSL certificate verification errors
- Change Correlator: Certificate rotation 15 minutes prior
- Topology Explainer: Auth service → Database dependency
- **Root Cause**: Database SSL certificate not updated in auth service
- **Remediation**: Update auth service config, restart

### Use Case 3: Network Degradation
**Symptoms**: Intermittent connectivity issues

**ADAPT Analysis**:
- Log Analyzer: Connection timeout patterns
- Metric Analyzer: Packet loss spike
- Change Correlator: Firewall rule changes
- Topology Explainer: Identifies critical path failure
- **Root Cause**: Overly restrictive firewall rules
- **Remediation**: Revert firewall changes

## 🔧 Configuration

Create a configuration file `config.yaml`:

```yaml
execution_mode: adaptive
confidence_threshold: 0.7
enable_remediation_planning: true

agent_config:
  log_analyzer:
    focus_areas:
      - "timeout errors"
      - "connection errors"

  metric_analyzer:
    anomaly_threshold: 2.0
    metrics_of_interest:
      - "http_request_latency_ms"
      - "error_rate_percent"

connector_config:
  synthetic:
    endpoint: "examples/synthetic-incidents"

playbook_dir: "playbooks"
output_format: "both"
log_level: "INFO"
```

Load it in your code:

```python
from core import load_config

config = load_config('config.yaml')
```

## 🧪 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=agents --cov=connectors

# Run specific test file
pytest tests/test_rca_graph.py
```

## 📖 Documentation

- **[Architecture](docs/architecture.md)**: System design and data flows
- **[Design Decisions](docs/design-decisions.md)**: Rationale behind key choices
- **[Component Catalog](docs/component-catalog.md)**: Complete component reference
- **[Roadmap](docs/roadmap.md)**: Future plans and enhancements

## 🛣️ Roadmap

**v1.1 (Q2 2025)**: Enhanced connectors (Prometheus, Elasticsearch, CloudWatch)

**v1.2 (Q3 2025)**: LLM-powered agents for deeper analysis

**v2.0 (Q1 2026)**: Real-time RCA with streaming signals

**v3.0 (2027)**: Predictive RCA and auto-remediation

See [docs/roadmap.md](docs/roadmap.md) for details.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**High-priority contribution areas**:
- Connectors for popular observability tools
- Specialized diagnostic agents
- Playbooks for common incident types
- Documentation and tutorials
- Synthetic incident examples

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

ADAPT draws inspiration from:
- Google's SRE practices and incident management
- Meta's Sift automated root cause analysis
- Netflix's chaos engineering principles
- The broader SRE and observability community

## 📬 Contact & Community

- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: Q&A and community chat
- **Email**: adapt-framework@example.com

## 🌟 Star History

If you find ADAPT useful, please star the repository! ⭐

---

**Built with ❤️ for the SRE and DevOps community**
