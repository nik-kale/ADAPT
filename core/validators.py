"""
Input validation and data quality checks for ADAPT framework.

This module provides validators for signals, configurations, and other
inputs to ensure data quality and prevent errors.
"""

from typing import Optional, Tuple, List
from datetime import datetime
import logging

from .signal_normalizer import NormalizedSignal
from .rca_graph import RCANode, RCAEdge, NodeType, EdgeType

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when validation fails"""
    pass


class SignalValidator:
    """Validates signals before processing"""

    @staticmethod
    def validate_signal(signal: NormalizedSignal) -> Tuple[bool, Optional[str]]:
        """
        Validate a signal for required fields and data quality.

        Args:
            signal: The signal to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not signal.timestamp:
            return False, "Signal missing timestamp"

        if signal.timestamp > datetime.utcnow():
            return False, f"Signal timestamp in future: {signal.timestamp}"

        if not signal.source:
            return False, "Signal missing source identifier"

        if signal.severity not in ['low', 'medium', 'high', 'critical']:
            return False, f"Invalid severity: {signal.severity}"

        if not signal.title or len(signal.title.strip()) == 0:
            return False, "Signal missing title"

        if not signal.description or len(signal.description.strip()) == 0:
            return False, "Signal missing description"

        return True, None

    @staticmethod
    def validate_signals_batch(signals: List[NormalizedSignal]) -> Tuple[List[NormalizedSignal], List[str]]:
        """
        Validate a batch of signals and filter out invalid ones.

        Args:
            signals: List of signals to validate

        Returns:
            Tuple of (valid_signals, error_messages)
        """
        valid_signals = []
        errors = []

        for i, signal in enumerate(signals):
            is_valid, error = SignalValidator.validate_signal(signal)

            if is_valid:
                valid_signals.append(signal)
            else:
                errors.append(f"Signal {i}: {error}")
                logger.warning(f"Invalid signal at index {i}: {error}")

        return valid_signals, errors


class GraphValidator:
    """Validates RCA graph structure"""

    @staticmethod
    def validate_node(node: RCANode) -> Tuple[bool, Optional[str]]:
        """
        Validate an RCA node.

        Args:
            node: The node to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not node.id or len(node.id.strip()) == 0:
            return False, "Node missing ID"

        if not isinstance(node.type, NodeType):
            return False, f"Invalid node type: {node.type}"

        if not node.title or len(node.title.strip()) == 0:
            return False, "Node missing title"

        if node.confidence < 0.0 or node.confidence > 1.0:
            return False, f"Invalid confidence score: {node.confidence} (must be 0.0-1.0)"

        return True, None

    @staticmethod
    def validate_edge(edge: RCAEdge, graph_nodes: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate an RCA edge.

        Args:
            edge: The edge to validate
            graph_nodes: Dictionary of existing nodes in the graph

        Returns:
            Tuple of (is_valid, error_message)
        """
        if edge.source not in graph_nodes:
            return False, f"Source node not found: {edge.source}"

        if edge.target not in graph_nodes:
            return False, f"Target node not found: {edge.target}"

        if not isinstance(edge.type, EdgeType):
            return False, f"Invalid edge type: {edge.type}"

        if edge.weight < 0.0 or edge.weight > 1.0:
            return False, f"Invalid edge weight: {edge.weight} (must be 0.0-1.0)"

        return True, None


class ConfigValidator:
    """Validates ADAPT configuration"""

    @staticmethod
    def validate_execution_mode(mode: str) -> Tuple[bool, Optional[str]]:
        """Validate execution mode"""
        valid_modes = ['sequential', 'parallel', 'adaptive']

        if mode not in valid_modes:
            return False, f"Invalid execution mode: {mode}. Must be one of {valid_modes}"

        return True, None

    @staticmethod
    def validate_confidence_threshold(threshold: float) -> Tuple[bool, Optional[str]]:
        """Validate confidence threshold"""
        if threshold < 0.0 or threshold > 1.0:
            return False, f"Invalid confidence threshold: {threshold}. Must be 0.0-1.0"

        return True, None

    @staticmethod
    def validate_output_format(format: str) -> Tuple[bool, Optional[str]]:
        """Validate output format"""
        valid_formats = ['json', 'markdown', 'both']

        if format not in valid_formats:
            return False, f"Invalid output format: {format}. Must be one of {valid_formats}"

        return True, None
