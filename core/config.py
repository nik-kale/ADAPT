"""
Configuration Management

Handles loading and validation of ADAPT configuration.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import yaml
import json
from pathlib import Path


@dataclass
class ADAPTConfig:
    """
    Main configuration object for ADAPT framework.

    Attributes:
        execution_mode: How to run agents ('sequential', 'parallel', 'adaptive')
        agent_config: Configuration for each agent
        connector_config: Configuration for data connectors
        playbook_dir: Directory containing playbooks
        output_format: Format for RCA output ('json', 'markdown', 'both')
        log_level: Logging level
        max_concurrent_agents: Maximum number of agents to run in parallel
    """
    execution_mode: str = 'adaptive'
    agent_config: Dict[str, Any] = field(default_factory=dict)
    connector_config: Dict[str, Any] = field(default_factory=dict)
    playbook_dir: str = 'playbooks'
    output_format: str = 'both'
    log_level: str = 'INFO'
    max_concurrent_agents: int = 5
    confidence_threshold: float = 0.7
    enable_remediation_planning: bool = True

    # v3.0 - Multi-Tenancy
    multi_tenancy_enabled: bool = False
    default_tenant_id: str = 'default'
    tenant_isolation_enforcement: bool = True

    # v3.0 - Audit Logging
    audit_enabled: bool = True
    audit_storage_backend: str = 'file'  # 'file', 'elasticsearch', 'database'
    audit_storage_path: str = './data/audit'
    audit_retention_days: int = 90

    # v3.0 - PII Scrubbing
    pii_scrubbing_enabled: bool = False
    pii_scrub_signals: bool = True
    pii_scrub_results: bool = True
    pii_hash_instead_of_redact: bool = False

    # v3.0 - Knowledge Base
    knowledge_base_enabled: bool = False
    knowledge_base_persist_dir: str = './data/knowledge'
    knowledge_base_similarity_threshold: float = 0.6

    # v3.0 - Auto-Remediation
    auto_remediation_enabled: bool = False
    auto_remediation_auto_approve_low_risk: bool = True
    auto_remediation_max_concurrent: int = 3
    auto_remediation_timeout: int = 300

    # v3.0 - Predictive Detection
    predictive_detection_enabled: bool = False
    prediction_window_hours: int = 1
    prediction_confidence_threshold: float = 0.6

    # v3.0 - LLM Integration
    llm_enabled: bool = False
    llm_provider: str = 'anthropic'  # 'anthropic', 'openai'
    llm_model: str = 'claude-3-sonnet-20240229'
    llm_api_key_env: str = 'ANTHROPIC_API_KEY'
    llm_max_tokens: int = 4096

    # v3.0 - OpenTelemetry
    telemetry_enabled: bool = False
    otlp_endpoint: str = 'http://localhost:4317'
    telemetry_service_name: str = 'adapt-rca'

    # v3.0 - Graph Storage
    graph_storage_enabled: bool = False
    graph_storage_backend: str = 'neo4j'  # 'neo4j', 'memory'
    neo4j_uri: str = 'bolt://localhost:7687'
    neo4j_username: str = 'neo4j'
    neo4j_password_env: str = 'NEO4J_PASSWORD'

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return asdict(self)

    def to_yaml(self) -> str:
        """Convert configuration to YAML string"""
        return yaml.dump(self.to_dict(), default_flow_style=False)

    def to_json(self, indent: int = 2) -> str:
        """Convert configuration to JSON string"""
        return json.dumps(self.to_dict(), indent=indent)


def load_config(config_path: Optional[str] = None) -> ADAPTConfig:
    """
    Load ADAPT configuration from file or use defaults.

    Args:
        config_path: Path to configuration file (YAML or JSON)

    Returns:
        ADAPTConfig instance

    Raises:
        FileNotFoundError: If config_path is specified but file doesn't exist
        ValueError: If configuration format is invalid
    """
    if config_path is None:
        # Return default configuration
        return ADAPTConfig()

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # Load configuration based on file extension
    with open(path, 'r') as f:
        if path.suffix in ['.yaml', '.yml']:
            config_data = yaml.safe_load(f)
        elif path.suffix == '.json':
            config_data = json.load(f)
        else:
            raise ValueError(f"Unsupported configuration format: {path.suffix}")

    # Create ADAPTConfig from loaded data
    return ADAPTConfig(**config_data)


def save_config(config: ADAPTConfig, config_path: str) -> None:
    """
    Save ADAPT configuration to file.

    Args:
        config: ADAPTConfig instance to save
        config_path: Path where configuration should be saved

    Raises:
        ValueError: If file format is not supported
    """
    path = Path(config_path)

    with open(path, 'w') as f:
        if path.suffix in ['.yaml', '.yml']:
            yaml.dump(config.to_dict(), f, default_flow_style=False)
        elif path.suffix == '.json':
            json.dump(config.to_dict(), f, indent=2)
        else:
            raise ValueError(f"Unsupported configuration format: {path.suffix}")
