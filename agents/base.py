"""
Base Agent Interface

Abstract base class for all diagnostic agents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class AgentResult:
    """
    Result returned by a diagnostic agent.

    Attributes:
        agent_name: Name of the agent that produced this result
        findings: List of findings (each with id, title, description, confidence, metadata)
        hypotheses: List of hypotheses generated
        metadata: Additional metadata about the execution
        execution_time: Time taken to execute (seconds)
        success: Whether the agent executed successfully
        error: Error message if execution failed
    """
    agent_name: str
    findings: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            'agent_name': self.agent_name,
            'findings': self.findings,
            'hypotheses': self.hypotheses,
            'metadata': self.metadata,
            'execution_time': self.execution_time,
            'success': self.success,
            'error': self.error,
        }


class BaseAgent(ABC):
    """
    Abstract base class for all diagnostic agents.

    All agents must implement the execute() method to perform their
    specific diagnostic tasks.
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent.

        Args:
            name: Unique name for this agent
            config: Agent-specific configuration
        """
        self.name = name
        self.config = config or {}

    @abstractmethod
    async def execute(self, context: Any) -> AgentResult:
        """
        Execute the agent's diagnostic logic.

        Args:
            context: OrchestrationContext containing signals and RCA graph

        Returns:
            AgentResult containing findings and hypotheses
        """
        pass

    def _create_finding(
        self,
        finding_id: str,
        title: str,
        description: str,
        confidence: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Helper method to create a standardized finding.

        Args:
            finding_id: Unique identifier for the finding
            title: Short title
            description: Detailed description
            confidence: Confidence score (0.0 to 1.0)
            metadata: Additional metadata

        Returns:
            Finding dictionary
        """
        return {
            'id': finding_id,
            'title': title,
            'description': description,
            'confidence': confidence,
            'metadata': metadata or {},
            'agent': self.name,
            'timestamp': datetime.utcnow().isoformat(),
        }

    def _create_hypothesis(
        self,
        hypothesis_id: str,
        title: str,
        description: str,
        requires_tests: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Helper method to create a standardized hypothesis.

        Args:
            hypothesis_id: Unique identifier
            title: Short title
            description: Detailed description
            requires_tests: List of tests needed to validate this hypothesis
            metadata: Additional metadata

        Returns:
            Hypothesis dictionary
        """
        return {
            'id': hypothesis_id,
            'title': title,
            'description': description,
            'requires_tests': requires_tests or [],
            'metadata': metadata or {},
            'agent': self.name,
            'timestamp': datetime.utcnow().isoformat(),
        }
