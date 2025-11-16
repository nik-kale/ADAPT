# Component Catalog

Complete reference for all ADAPT components, their purposes, and interfaces.

## Core Components

### RCA Graph (`core/rca_graph.py`)

#### `RCANode`
Represents a node in the RCA graph.

**Attributes:**
- `id` (str): Unique identifier
- `type` (NodeType): Type of node (symptom, hypothesis, test, finding, root_cause, contributing_factor)
- `title` (str): Short description
- `description` (str): Detailed description
- `confidence` (float): Confidence score (0.0 to 1.0)
- `metadata` (dict): Additional context
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last update timestamp

**Methods:**
- `to_dict()`: Convert to dictionary representation

#### `RCAEdge`
Represents a relationship between nodes.

**Attributes:**
- `source` (str): Source node ID
- `target` (str): Target node ID
- `type` (EdgeType): Relationship type (suggests, requires, confirms, refutes, causes, contributes_to)
- `weight` (float): Relationship strength (0.0 to 1.0)
- `metadata` (dict): Additional context
- `created_at` (datetime): Creation timestamp

#### `RCAGraph`
The main graph structure.

**Methods:**
- `add_node(node)`: Add a node to the graph
- `add_edge(edge)`: Add an edge to the graph
- `get_node(node_id)`: Retrieve node by ID
- `get_nodes_by_type(node_type)`: Get all nodes of a specific type
- `get_outgoing_edges(node_id)`: Get edges from a node
- `get_incoming_edges(node_id)`: Get edges to a node
- `get_root_causes()`: Get all root cause nodes
- `traverse_from_symptom(symptom_id)`: Traverse graph from symptom
- `to_dict()`: Export to dictionary
- `to_json()`: Export to JSON string
- `export_narrative()`: Generate human-readable narrative

### Orchestrator (`core/orchestrator.py`)

#### `OrchestrationContext`
Holds state during RCA session.

**Attributes:**
- `incident_id` (str): Incident identifier
- `graph` (RCAGraph): The RCA graph being built
- `signals` (list): Normalized input signals
- `agent_results` (dict): Results from each agent
- `start_time` (datetime): Session start time
- `end_time` (datetime): Session end time
- `metadata` (dict): Additional context

#### `RCAOrchestrator`
Coordinates the RCA workflow.

**Methods:**
- `register_agent(name, instance)`: Register a diagnostic agent
- `run_rca(incident_id, signals, playbook)`: Execute complete RCA workflow
- `_identify_symptoms(context)`: Extract symptoms from signals
- `_run_agents_sequential(context)`: Run agents sequentially
- `_run_agents_parallel(context)`: Run agents in parallel
- `_run_agents_adaptive(context)`: Run agents adaptively
- `_synthesize_findings(context)`: Aggregate agent findings
- `_identify_root_causes(context)`: Promote findings to root causes
- `_generate_remediation_plan(context)`: Generate action plan

### Configuration (`core/config.py`)

#### `ADAPTConfig`
Framework configuration.

**Attributes:**
- `execution_mode` (str): Agent execution mode (sequential, parallel, adaptive)
- `agent_config` (dict): Per-agent configuration
- `connector_config` (dict): Connector configuration
- `playbook_dir` (str): Playbook directory path
- `output_format` (str): Output format (json, markdown, both)
- `log_level` (str): Logging level
- `max_concurrent_agents` (int): Max parallel agents
- `confidence_threshold` (float): Minimum confidence for root causes
- `enable_remediation_planning` (bool): Enable remediation planning

**Functions:**
- `load_config(path)`: Load configuration from file
- `save_config(config, path)`: Save configuration to file

### Signal Normalizer (`core/signal_normalizer.py`)

#### `NormalizedSignal`
Unified signal representation.

**Attributes:**
- `signal_type` (SignalType): Type (log, metric, trace, config_change, alert, event)
- `title` (str): Short description
- `description` (str): Detailed description
- `timestamp` (datetime): Signal timestamp
- `source` (str): Origin identifier
- `severity` (str): Severity level
- `raw_data` (any): Original data
- `metadata` (dict): Additional context
- `tags` (dict): Key-value tags

#### `SignalNormalizer`
Converts raw data to normalized signals.

**Static Methods:**
- `normalize_log_entry(log_entry, source)`: Normalize a log entry
- `normalize_metric(metric_data, source)`: Normalize a metric
- `normalize_config_change(change_data, source)`: Normalize a config change
- `normalize_batch(raw_signals, signal_type, source)`: Batch normalize

## Diagnostic Agents

### Base Agent (`agents/base.py`)

#### `AgentResult`
Standardized agent result.

**Attributes:**
- `agent_name` (str): Name of the agent
- `findings` (list): List of findings
- `hypotheses` (list): List of hypotheses
- `metadata` (dict): Additional metadata
- `execution_time` (float): Execution duration
- `success` (bool): Whether execution succeeded
- `error` (str): Error message if failed

#### `BaseAgent`
Abstract base class for agents.

**Methods:**
- `execute(context)`: Perform diagnostic analysis (abstract)
- `_create_finding(...)`: Helper to create a finding
- `_create_hypothesis(...)`: Helper to create a hypothesis

### Log Analyzer Agent (`agents/log_analyzer.py`)

**Purpose**: Analyze log data for error patterns, anomalies, and correlations.

**Analysis Techniques:**
- Error rate spike detection
- Pattern matching against known error types
- Temporal correlation analysis
- Cross-service error correlation

**Findings Produced:**
- Error rate spikes with timestamps
- Matched error patterns by category
- First error occurrence
- Multiple service impacts

**Configuration Options:**
- `focus_areas`: Specific error types to focus on
- Custom error patterns

### Metric Analyzer Agent (`agents/metric_analyzer.py`)

**Purpose**: Analyze metric data for anomalies, trends, and threshold breaches.

**Analysis Techniques:**
- Statistical anomaly detection (z-score)
- Threshold breach detection
- Trend analysis (comparing time windows)
- Metric correlation analysis

**Findings Produced:**
- Metric anomalies with z-scores
- Threshold breaches
- Trend directions and magnitudes
- Correlated metric anomalies

**Configuration Options:**
- `anomaly_threshold`: Z-score threshold for anomalies (default: 2.0)
- `metrics_of_interest`: Specific metrics to analyze

### Topology Explainer Agent (`agents/topology_explainer.py`)

**Purpose**: Analyze service dependencies and failure propagation.

**Analysis Techniques:**
- Service dependency mapping
- Root service identification
- Failure propagation analysis
- Critical path analysis
- Single point of failure detection

**Findings Produced:**
- Root services causing downstream issues
- Failure propagation chains
- Critical service impacts
- Single points of failure

**Configuration Options:**
- `topology_map`: Service topology definition
- `focus_services`: Specific services to analyze

### Change Correlator Agent (`agents/change_correlator.py`)

**Purpose**: Correlate configuration changes and deployments with incidents.

**Analysis Techniques:**
- Temporal correlation (change timing vs symptom onset)
- Change cluster detection
- High-risk component identification
- Rollback opportunity identification

**Findings Produced:**
- Changes correlated with symptoms
- Change clusters
- High-risk component changes
- Rollback opportunities

**Configuration Options:**
- `correlation_window_minutes`: Time window for correlation (default: 30)
- `focus_components`: Specific components to monitor

### Remediation Planner Agent (`agents/remediation_planner.py`)

**Purpose**: Generate actionable remediation plans based on findings.

**Analysis Techniques:**
- Finding categorization
- Template-based action generation
- Risk assessment
- Action prioritization
- Validation step generation

**Output Structure:**
- Prioritized list of remediation actions
- Risk assessment for each action
- Estimated time per action
- Rollback procedures
- Validation steps

**Configuration Options:**
- Custom remediation templates
- Risk assessment rules

## Connectors

### Base Connector (`connectors/base.py`)

#### `ConnectorConfig`
Connector configuration.

**Attributes:**
- `connector_type` (str): Type of connector
- `endpoint` (str): Connection endpoint
- `credentials` (dict): Authentication credentials
- `filters` (dict): Default filters
- `batch_size` (int): Batch size for fetching

#### `BaseConnector`
Abstract base class for connectors.

**Methods:**
- `connect()`: Establish connection (abstract)
- `disconnect()`: Close connection (abstract)
- `fetch_logs(start_time, end_time, filters)`: Fetch logs (abstract)
- `fetch_metrics(start_time, end_time, metric_names, filters)`: Fetch metrics (abstract)
- `fetch_config_changes(start_time, end_time, components)`: Fetch changes (abstract)
- `fetch_all_signals(start_time, end_time, signal_types)`: Fetch all signals

### Synthetic Connector (`connectors/synthetic_connector.py`)

**Purpose**: Provide synthetic data for testing and demonstrations.

**Capabilities:**
- Load pre-generated data from JSON files
- Generate random synthetic data on-the-fly
- Replay incident scenarios

**Data Files:**
- `logs.json`: Log entries
- `metrics.json`: Metric data points
- `config_changes.json`: Configuration changes

**Methods:**
- All BaseConnector methods implemented
- `_load_data()`: Load data from files
- `_generate_synthetic_logs()`: Generate random logs
- `_generate_synthetic_metrics()`: Generate random metrics
- `_generate_synthetic_config_changes()`: Generate random changes

## Playbooks

### Playbook Structure

Playbooks are YAML files that define incident scenarios.

**Required Fields:**
- `name`: Playbook name
- `description`: What this playbook addresses
- `version`: Playbook version
- `category`: Incident category

**Optional Sections:**
- `metadata`: Additional metadata
- `triggers`: What triggers this playbook
- `initial_symptoms`: Expected symptoms
- `agent_configuration`: Agent settings for this playbook
- `common_root_causes`: Known root causes with probabilities
- `investigation_steps`: Structured investigation procedure
- `remediation_strategies`: Recommended remediation approaches
- `success_criteria`: How to validate resolution

### Available Playbooks

1. **latency-regression.yaml**: API latency spikes
2. **auth-service-failure.yaml**: Authentication service issues
3. **network-degradation.yaml**: Network connectivity problems

## UI Examples

### Chat Interface Outputs

**rca_chat_response.json**: Complete RCA analysis formatted for chat interfaces

**progressive_analysis.json**: Streaming updates as RCA progresses

### Dashboard Widgets

**rca_summary_widget.json**: Summary widget showing RCA progress and key findings

**rca_graph_visualization.json**: Interactive graph visualization configuration

## Extension Points

### Creating a Custom Agent

```python
from agents.base import BaseAgent, AgentResult

class MyCustomAgent(BaseAgent):
    def __init__(self, config=None):
        super().__init__(name='my_custom_agent', config=config)

    async def execute(self, context):
        # Your analysis logic here
        findings = []

        # Create findings
        findings.append(
            self._create_finding(
                finding_id='custom_001',
                title='Custom Finding',
                description='Found something interesting',
                confidence=0.8
            )
        )

        return AgentResult(
            agent_name=self.name,
            findings=findings,
            success=True
        )
```

### Creating a Custom Connector

```python
from connectors.base import BaseConnector, ConnectorConfig

class MyCustomConnector(BaseConnector):
    async def connect(self):
        # Connect to your data source
        return True

    async def disconnect(self):
        # Clean up connection
        pass

    async def fetch_logs(self, start_time, end_time, filters=None):
        # Fetch and normalize logs
        return []

    async def fetch_metrics(self, start_time, end_time, metric_names=None, filters=None):
        # Fetch and normalize metrics
        return []

    async def fetch_config_changes(self, start_time, end_time, components=None):
        # Fetch and normalize config changes
        return []
```
