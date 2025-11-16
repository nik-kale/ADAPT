"""
Tests for validation infrastructure.
"""

import pytest
from datetime import datetime, timedelta

from core.validators import SignalValidator, GraphValidator, ConfigValidator, ValidationError
from core.signal_normalizer import NormalizedSignal, SignalType
from core.rca_graph import RCANode, RCAEdge, NodeType, EdgeType


class TestSignalValidator:
    """Tests for SignalValidator"""

    def test_valid_signal(self, sample_log_signals):
        """Test validation of a valid signal"""
        signal = sample_log_signals[0]
        is_valid, error = SignalValidator.validate_signal(signal)

        assert is_valid is True
        assert error is None

    def test_missing_timestamp(self):
        """Test signal with missing timestamp"""
        signal = NormalizedSignal(
            signal_type=SignalType.LOG,
            title="Test",
            description="Test description",
            timestamp=None,
            source="test",
            severity="high"
        )

        is_valid, error = SignalValidator.validate_signal(signal)

        assert is_valid is False
        assert "timestamp" in error.lower()

    def test_future_timestamp(self):
        """Test signal with future timestamp"""
        future_time = datetime.utcnow() + timedelta(hours=1)
        signal = NormalizedSignal(
            signal_type=SignalType.LOG,
            title="Test",
            description="Test description",
            timestamp=future_time,
            source="test",
            severity="high"
        )

        is_valid, error = SignalValidator.validate_signal(signal)

        assert is_valid is False
        assert "future" in error.lower()

    def test_invalid_severity(self):
        """Test signal with invalid severity"""
        signal = NormalizedSignal(
            signal_type=SignalType.LOG,
            title="Test",
            description="Test description",
            timestamp=datetime.utcnow(),
            source="test",
            severity="invalid"
        )

        is_valid, error = SignalValidator.validate_signal(signal)

        assert is_valid is False
        assert "severity" in error.lower()

    def test_validate_batch(self, sample_log_signals):
        """Test batch validation"""
        # Add an invalid signal
        invalid_signal = NormalizedSignal(
            signal_type=SignalType.LOG,
            title="",  # Empty title
            description="Test",
            timestamp=datetime.utcnow(),
            source="test",
            severity="high"
        )

        signals = sample_log_signals + [invalid_signal]
        valid_signals, errors = SignalValidator.validate_signals_batch(signals)

        assert len(valid_signals) == len(sample_log_signals)
        assert len(errors) == 1


class TestGraphValidator:
    """Tests for GraphValidator"""

    def test_valid_node(self, sample_rca_node):
        """Test validation of a valid node"""
        is_valid, error = GraphValidator.validate_node(sample_rca_node)

        assert is_valid is True
        assert error is None

    def test_missing_node_id(self):
        """Test node with missing ID"""
        node = RCANode(
            id="",
            type=NodeType.SYMPTOM,
            title="Test",
            description="Test description"
        )

        is_valid, error = GraphValidator.validate_node(node)

        assert is_valid is False
        assert "id" in error.lower()

    def test_invalid_confidence(self):
        """Test node with invalid confidence score"""
        node = RCANode(
            id="test",
            type=NodeType.FINDING,
            title="Test",
            description="Test",
            confidence=1.5  # Invalid: > 1.0
        )

        is_valid, error = GraphValidator.validate_node(node)

        assert is_valid is False
        assert "confidence" in error.lower()

    def test_valid_edge(self, sample_graph, sample_rca_node):
        """Test validation of a valid edge"""
        # Add nodes to graph
        node1 = sample_rca_node
        node2 = RCANode(
            id="finding_1",
            type=NodeType.FINDING,
            title="Finding",
            description="Test finding"
        )

        sample_graph.add_node(node1)
        sample_graph.add_node(node2)

        edge = RCAEdge(
            source=node1.id,
            target=node2.id,
            type=EdgeType.SUGGESTS
        )

        is_valid, error = GraphValidator.validate_edge(edge, sample_graph.nodes)

        assert is_valid is True
        assert error is None

    def test_edge_missing_source(self, sample_graph):
        """Test edge with non-existent source node"""
        edge = RCAEdge(
            source="nonexistent",
            target="also_nonexistent",
            type=EdgeType.SUGGESTS
        )

        is_valid, error = GraphValidator.validate_edge(edge, sample_graph.nodes)

        assert is_valid is False
        assert "source" in error.lower()


class TestConfigValidator:
    """Tests for ConfigValidator"""

    def test_valid_execution_mode(self):
        """Test validation of valid execution mode"""
        is_valid, error = ConfigValidator.validate_execution_mode('adaptive')

        assert is_valid is True
        assert error is None

    def test_invalid_execution_mode(self):
        """Test validation of invalid execution mode"""
        is_valid, error = ConfigValidator.validate_execution_mode('invalid')

        assert is_valid is False
        assert "execution mode" in error.lower()

    def test_valid_confidence_threshold(self):
        """Test validation of valid confidence threshold"""
        is_valid, error = ConfigValidator.validate_confidence_threshold(0.7)

        assert is_valid is True
        assert error is None

    def test_invalid_confidence_threshold(self):
        """Test validation of invalid confidence threshold"""
        is_valid, error = ConfigValidator.validate_confidence_threshold(1.5)

        assert is_valid is False
        assert "confidence threshold" in error.lower()

    def test_valid_output_format(self):
        """Test validation of valid output format"""
        is_valid, error = ConfigValidator.validate_output_format('both')

        assert is_valid is True
        assert error is None

    def test_invalid_output_format(self):
        """Test validation of invalid output format"""
        is_valid, error = ConfigValidator.validate_output_format('invalid')

        assert is_valid is False
        assert "output format" in error.lower()
