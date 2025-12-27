"""
RCA Graph Export and Visualization

Provides utilities for exporting RCA graphs to various formats:
- DOT (Graphviz) for visualization
- JSON for web UIs
- NetworkX for analysis
"""

from typing import Dict, Any, Optional
import json

from core.rca_graph import RCAGraph, NodeType, EdgeType


class GraphExporter:
    """
    Export RCA graphs to various formats.
    
    Supports:
    - DOT format for Graphviz visualization
    - JSON format for web UIs
    - NetworkX format for graph analysis
    """
    
    @staticmethod
    def to_dot(graph: RCAGraph, include_metadata: bool = False) -> str:
        """
        Export graph to DOT format for Graphviz.
        
        Args:
            graph: RCA graph to export
            include_metadata: Whether to include node metadata in labels
            
        Returns:
            DOT format string
        """
        lines = ['digraph RCA {']
        lines.append('    rankdir=TB;')  # Top to bottom
        lines.append('    node [shape=box, style=rounded];')
        lines.append('')
        
        # Node colors by type
        colors = {
            NodeType.SYMPTOM: '#ffcccc',
            NodeType.HYPOTHESIS: '#cce5ff',
            NodeType.TEST: '#ffffcc',
            NodeType.FINDING: '#ccffcc',
            NodeType.ROOT_CAUSE: '#ffccff',
            NodeType.CONTRIBUTING_FACTOR: '#e6ccff',
        }
        
        # Add nodes
        for node in graph.nodes.values():
            color = colors.get(node.type, '#ffffff')
            label = node.title.replace('"', '\\"')
            
            if include_metadata and node.confidence > 0:
                label += f"\\n(confidence: {node.confidence:.2f})"
            
            lines.append(
                f'    "{node.id}" [label="{label}", '
                f'fillcolor="{color}", style=filled];'
            )
        
        lines.append('')
        
        # Add edges
        for edge in graph.edges:
            style = 'solid'
            if edge.type == EdgeType.REFUTES:
                style = 'dashed'
            elif edge.type == EdgeType.SUGGESTS:
                style = 'dotted'
            
            label = edge.type.value
            lines.append(
                f'    "{edge.source}" -> "{edge.target}" '
                f'[label="{label}", style={style}];'
            )
        
        lines.append('}')
        return '\n'.join(lines)
    
    @staticmethod
    def to_json(graph: RCAGraph, pretty: bool = True) -> str:
        """
        Export graph to JSON format.
        
        Args:
            graph: RCA graph to export
            pretty: Whether to pretty-print JSON
            
        Returns:
            JSON string
        """
        data = {
            'incident_id': graph.incident_id,
            'nodes': [node.to_dict() for node in graph.nodes.values()],
            'edges': [edge.to_dict() for edge in graph.edges],
            'metadata': {
                'node_count': len(graph.nodes),
                'edge_count': len(graph.edges),
                'root_causes': [
                    node.to_dict() for node in graph.get_root_causes()
                ]
            }
        }
        
        if pretty:
            return json.dumps(data, indent=2)
        return json.dumps(data)
    
    @staticmethod
    def to_networkx(graph: RCAGraph) -> Any:
        """
        Export to NetworkX DiGraph for analysis.
        
        Args:
            graph: RCA graph to export
            
        Returns:
            NetworkX DiGraph object
            
        Raises:
            ImportError: If networkx not installed
        """
        try:
            import networkx as nx
        except ImportError:
            raise ImportError(
                "NetworkX required for this export format. "
                "Install with: pip install networkx"
            )
        
        G = nx.DiGraph()
        
        # Add nodes with attributes
        for node in graph.nodes.values():
            G.add_node(
                node.id,
                type=node.type.value,
                title=node.title,
                confidence=node.confidence,
                **node.metadata
            )
        
        # Add edges with attributes
        for edge in graph.edges:
            G.add_edge(
                edge.source,
                edge.target,
                type=edge.type.value,
                weight=edge.weight,
                **edge.metadata
            )
        
        return G
    
    @staticmethod
    def to_mermaid(graph: RCAGraph) -> str:
        """
        Export graph to Mermaid diagram format.
        
        Args:
            graph: RCA graph to export
            
        Returns:
            Mermaid format string
        """
        lines = ['graph TD']
        
        # Style classes by node type
        styles = {
            NodeType.SYMPTOM: 'fill:#ffcccc',
            NodeType.HYPOTHESIS: 'fill:#cce5ff',
            NodeType.TEST: 'fill:#ffffcc',
            NodeType.FINDING: 'fill:#ccffcc',
            NodeType.ROOT_CAUSE: 'fill:#ffccff',
            NodeType.CONTRIBUTING_FACTOR: 'fill:#e6ccff',
        }
        
        # Add nodes
        node_styles = {}
        for node in graph.nodes.values():
            safe_id = node.id.replace('-', '_')
            label = node.title.replace('"', "'")
            lines.append(f'    {safe_id}["{label}"]')
            node_styles[safe_id] = styles.get(node.type, '')
        
        # Add edges
        for edge in graph.edges:
            safe_source = edge.source.replace('-', '_')
            safe_target = edge.target.replace('-', '_')
            label = edge.type.value
            lines.append(f'    {safe_source} -->|{label}| {safe_target}')
        
        # Add styles
        for node_id, style in node_styles.items():
            if style:
                lines.append(f'    style {node_id} {style}')
        
        return '\n'.join(lines)


def export_graph(
    graph: RCAGraph,
    output_file: str,
    format: str = 'auto'
) -> None:
    """
    Export graph to file.
    
    Args:
        graph: RCA graph to export
        output_file: Output file path
        format: Export format ('dot', 'json', 'mermaid', or 'auto')
    """
    from pathlib import Path
    
    path = Path(output_file)
    
    # Auto-detect format from extension
    if format == 'auto':
        ext = path.suffix.lower()
        if ext == '.dot':
            format = 'dot'
        elif ext == '.json':
            format = 'json'
        elif ext == '.mmd' or ext == '.mermaid':
            format = 'mermaid'
        else:
            format = 'json'  # Default
    
    # Export based on format
    exporter = GraphExporter()
    
    if format == 'dot':
        content = exporter.to_dot(graph, include_metadata=True)
    elif format == 'json':
        content = exporter.to_json(graph, pretty=True)
    elif format == 'mermaid':
        content = exporter.to_mermaid(graph)
    else:
        raise ValueError(f"Unsupported format: {format}")
    
    # Write to file
    with open(path, 'w') as f:
        f.write(content)

