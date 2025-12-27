"""
Tests for Graph Export Utilities
"""

import pytest
import tempfile
import json
from pathlib import Path

from core.rca_graph import RCAGraph, RCANode, RCAEdge, NodeType, EdgeType
from core.graph_export import GraphExporter, export_graph


class TestGraphExporter:
    """Tests for GraphExporter class"""
    
    def setup_method(self):
        """Create test graph"""
        self.graph = RCAGraph(incident_id="test_001")
        
        # Add nodes
        symptom = RCANode(
            id="symptom_1",
            type=NodeType.SYMPTOM,
            title="High Latency",
            description="API latency increased",
            confidence=0.9
        )
        
        hypothesis = RCANode(
            id="hypothesis_1",
            type=NodeType.HYPOTHESIS,
            title="Database Slowdown",
            description="Database queries are slow",
            confidence=0.7
        )
        
        root_cause = RCANode(
            id="root_cause_1",
            type=NodeType.ROOT_CAUSE,
            title="Missing Index",
            description="Table missing index",
            confidence=0.95
        )
        
        self.graph.add_node(symptom)
        self.graph.add_node(hypothesis)
        self.graph.add_node(root_cause)
        
        # Add edges
        self.graph.add_edge(RCAEdge(
            source="symptom_1",
            target="hypothesis_1",
            type=EdgeType.SUGGESTS,
            weight=0.8
        ))
        
        self.graph.add_edge(RCAEdge(
            source="hypothesis_1",
            target="root_cause_1",
            type=EdgeType.CONFIRMS,
            weight=0.9
        ))
    
    def test_to_dot(self):
        """Test DOT format export"""
        exporter = GraphExporter()
        dot_output = exporter.to_dot(self.graph, include_metadata=True)
        
        assert "digraph RCA" in dot_output
        assert "symptom_1" in dot_output
        assert "High Latency" in dot_output
        assert "confidence: 0.90" in dot_output
    
    def test_to_json(self):
        """Test JSON format export"""
        exporter = GraphExporter()
        json_output = exporter.to_json(self.graph, pretty=True)
        
        data = json.loads(json_output)
        
        assert data['incident_id'] == "test_001"
        assert len(data['nodes']) == 3
        assert len(data['edges']) == 2
        assert 'metadata' in data
    
    def test_to_mermaid(self):
        """Test Mermaid format export"""
        exporter = GraphExporter()
        mermaid_output = exporter.to_mermaid(self.graph)
        
        assert "graph TD" in mermaid_output
        assert "symptom_1" in mermaid_output
        assert "High Latency" in mermaid_output
    
    def test_to_networkx(self):
        """Test NetworkX export"""
        pytest.importorskip("networkx")
        
        exporter = GraphExporter()
        nx_graph = exporter.to_networkx(self.graph)
        
        assert len(nx_graph.nodes) == 3
        assert len(nx_graph.edges) == 2
        assert "symptom_1" in nx_graph.nodes
    
    def test_networkx_import_error(self):
        """Test NetworkX export without networkx installed"""
        import sys
        import importlib
        
        # Mock missing networkx
        original_import = __builtins__.__import__
        
        def mock_import(name, *args, **kwargs):
            if name == 'networkx':
                raise ImportError("No module named 'networkx'")
            return original_import(name, *args, **kwargs)
        
        __builtins__.__import__ = mock_import
        
        try:
            exporter = GraphExporter()
            with pytest.raises(ImportError, match="NetworkX required"):
                exporter.to_networkx(self.graph)
        finally:
            __builtins__.__import__ = original_import


class TestExportGraph:
    """Tests for export_graph convenience function"""
    
    def setup_method(self):
        """Create test graph"""
        self.graph = RCAGraph(incident_id="test_001")
        node = RCANode(
            id="test_node",
            type=NodeType.SYMPTOM,
            title="Test",
            description="Test node"
        )
        self.graph.add_node(node)
    
    def test_export_dot_file(self):
        """Test exporting to DOT file"""
        with tempfile.NamedTemporaryFile(suffix='.dot', delete=False) as f:
            temp_path = f.name
        
        try:
            export_graph(self.graph, temp_path, format='auto')
            
            assert Path(temp_path).exists()
            content = Path(temp_path).read_text()
            assert "digraph RCA" in content
        finally:
            Path(temp_path).unlink()
    
    def test_export_json_file(self):
        """Test exporting to JSON file"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            export_graph(self.graph, temp_path, format='auto')
            
            assert Path(temp_path).exists()
            with open(temp_path) as f:
                data = json.load(f)
            assert data['incident_id'] == "test_001"
        finally:
            Path(temp_path).unlink()
    
    def test_export_mermaid_file(self):
        """Test exporting to Mermaid file"""
        with tempfile.NamedTemporaryFile(suffix='.mmd', delete=False) as f:
            temp_path = f.name
        
        try:
            export_graph(self.graph, temp_path, format='auto')
            
            assert Path(temp_path).exists()
            content = Path(temp_path).read_text()
            assert "graph TD" in content
        finally:
            Path(temp_path).unlink()
    
    def test_unsupported_format(self):
        """Test error on unsupported format"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Unsupported format"):
                export_graph(self.graph, temp_path, format='invalid')
        finally:
            Path(temp_path).unlink()

