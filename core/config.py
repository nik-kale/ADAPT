"""
Configuration Management

Handles loading and validation of ADAPT configuration.

v4.0: Enhanced with Pydantic validation and security-first defaults
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Dict, List, Optional, Any
import yaml
import json
import os
import logging
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Valid execution modes"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"


class LogLevel(str, Enum):
    """Valid log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class OutputFormat(str, Enum):
    """Valid output formats"""
    JSON = "json"
    MARKDOWN = "markdown"
    BOTH = "both"


class ADAPTConfig(BaseModel):
    """
    Main configuration object for ADAPT framework (v4.0).

    Enhanced with Pydantic validation for all fields.

    Attributes:
        execution_mode: How to run agents ('sequential', 'parallel', 'adaptive')
        agent_config: Configuration for each agent
        connector_config: Configuration for data connectors
        playbook_dir: Directory containing playbooks
        output_format: Format for RCA output ('json', 'markdown', 'both')
        log_level: Logging level
        max_concurrent_agents: Maximum number of agents to run in parallel
    """

    # Core settings
    execution_mode: ExecutionMode = ExecutionMode.ADAPTIVE
    agent_config: Dict[str, Any] = Field(default_factory=dict)
    connector_config: Dict[str, Any] = Field(default_factory=dict)
    playbook_dir: str = Field(default="playbooks", min_length=1)
    output_format: OutputFormat = OutputFormat.BOTH
    log_level: LogLevel = LogLevel.INFO
    max_concurrent_agents: int = Field(default=5, ge=1, le=100)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    enable_remediation_planning: bool = True

    # v3.0 - Multi-Tenancy
    multi_tenancy_enabled: bool = False
    default_tenant_id: str = Field(default="default", min_length=1)
    tenant_isolation_enforcement: bool = True

    # v3.0 - Audit Logging
    audit_enabled: bool = True
    audit_storage_backend: str = Field(
        default="file", pattern="^(file|elasticsearch|database)$"
    )
    audit_storage_path: str = Field(default="./data/audit", min_length=1)
    audit_retention_days: int = Field(default=90, ge=1, le=3650)

    # v3.0/v4.0 - PII Scrubbing (SECURITY: Now enabled by default!)
    pii_scrubbing_enabled: bool = True  # Changed from False to True in v4.0
    pii_scrub_signals: bool = True
    pii_scrub_results: bool = True
    pii_hash_instead_of_redact: bool = False

    # v3.0 - Knowledge Base
    knowledge_base_enabled: bool = False
    knowledge_base_persist_dir: str = Field(default="./data/knowledge", min_length=1)
    knowledge_base_similarity_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    # v3.0 - Auto-Remediation
    auto_remediation_enabled: bool = False
    auto_remediation_auto_approve_low_risk: bool = True
    auto_remediation_max_concurrent: int = Field(default=3, ge=1, le=20)
    auto_remediation_timeout: int = Field(default=300, ge=1, le=3600)

    # v3.0 - Predictive Detection
    predictive_detection_enabled: bool = False
    prediction_window_hours: int = Field(default=1, ge=1, le=168)
    prediction_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    # v3.0 - LLM Integration
    llm_enabled: bool = False
    llm_provider: str = Field(default="anthropic", pattern="^(anthropic|openai)$")
    llm_model: str = Field(default="claude-3-sonnet-20240229", min_length=1)
    llm_api_key_env: str = Field(default="ANTHROPIC_API_KEY", min_length=1)
    llm_max_tokens: int = Field(default=4096, ge=1, le=200000)

    # v3.0 - OpenTelemetry
    telemetry_enabled: bool = False
    otlp_endpoint: str = Field(default="http://localhost:4317", min_length=1)
    telemetry_service_name: str = Field(default="adapt-rca", min_length=1)

    # v3.0 - Graph Storage
    graph_storage_enabled: bool = False
    graph_storage_backend: str = Field(
        default="neo4j", pattern="^(neo4j|memory)$"
    )
    neo4j_uri: str = Field(default="bolt://localhost:7687", min_length=1)
    neo4j_username: str = Field(default="neo4j", min_length=1)
    neo4j_password_env: str = Field(default="NEO4J_PASSWORD", min_length=1)

    @model_validator(mode='after')
    def validate_production_security(self) -> 'ADAPTConfig':
        """Enforce security requirements in production (v4.0)"""
        environment = os.getenv("ENVIRONMENT", "development")

        if environment == "production":
            # PII scrubbing MUST be enabled in production
            if not self.pii_scrubbing_enabled:
                logger.critical(
                    "⚠️  CRITICAL: PII scrubbing is DISABLED in production environment!"
                )
                raise ValueError(
                    "pii_scrubbing_enabled must be True in production. "
                    "This is a security requirement to prevent data leakage."
                )

            # Audit logging MUST be enabled in production
            if not self.audit_enabled:
                logger.warning(
                    "⚠️  WARNING: Audit logging disabled in production. "
                    "This is not recommended for compliance."
                )

        return self

    @field_validator('neo4j_username')
    @classmethod
    def validate_no_default_credentials(cls, v: str) -> str:
        """Warn if using default credentials (v4.0 security)"""
        default_creds = ['neo4j', 'admin', 'postgres', 'root']
        if v.lower() in default_creds:
            logger.warning(
                f"⚠️  Using potentially default username: {v}. "
                "Ensure this is changed in production."
            )
        return v

    class Config:
        """Pydantic configuration"""
        use_enum_values = True
        validate_assignment = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return self.model_dump()

    def to_yaml(self) -> str:
        """Convert configuration to YAML string"""
        return yaml.dump(self.to_dict(), default_flow_style=False)

    def to_json(self, indent: int = 2) -> str:
        """Convert configuration to JSON string"""
        return json.dumps(self.to_dict(), indent=indent)


def load_config(config_path: Optional[str] = None) -> ADAPTConfig:
    """
    Load ADAPT configuration from file or use defaults (v4.0 enhanced).

    Args:
        config_path: Path to configuration file (YAML or JSON)

    Returns:
        ADAPTConfig instance (validated via Pydantic)

    Raises:
        FileNotFoundError: If config_path is specified but file doesn't exist
        ValueError: If configuration format is invalid or validation fails
    """
    if config_path is None:
        # Return default configuration (will be validated)
        return ADAPTConfig()

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # Load configuration based on file extension
    with open(path, 'r') as f:
        if path.suffix in ['.yaml', '.yml']:
            config_data = yaml.safe_load(f) or {}
        elif path.suffix == '.json':
            config_data = json.load(f)
        else:
            raise ValueError(f"Unsupported configuration format: {path.suffix}")

    # Create ADAPTConfig from loaded data (Pydantic validates automatically)
    try:
        return ADAPTConfig(**config_data)
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")


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
