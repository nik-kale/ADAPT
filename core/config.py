"""
Configuration Management

Handles loading and validation of ADAPT configuration.
"""

from dataclasses import dataclass, field
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'execution_mode': self.execution_mode,
            'agent_config': self.agent_config,
            'connector_config': self.connector_config,
            'playbook_dir': self.playbook_dir,
            'output_format': self.output_format,
            'log_level': self.log_level,
            'max_concurrent_agents': self.max_concurrent_agents,
            'confidence_threshold': self.confidence_threshold,
            'enable_remediation_planning': self.enable_remediation_planning,
        }

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
