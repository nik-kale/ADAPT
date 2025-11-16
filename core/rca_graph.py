"""
RCA Graph Model

The core data structure for representing root cause analysis as a directed graph.
Nodes represent symptoms, hypotheses, tests, and findings.
Edges represent causal relationships and dependencies.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum
from datetime import datetime
import json


class NodeType(Enum):
    """Types of nodes in the RCA graph"""
    SYMPTOM = "symptom"              # Observable issue (e.g., high latency)
    HYPOTHESIS = "hypothesis"        # Potential cause to investigate
    TEST = "test"                    # Diagnostic test or check
    FINDING = "finding"              # Confirmed observation
    ROOT_CAUSE = "root_cause"        # Identified root cause
    CONTRIBUTING_FACTOR = "contributing_factor"  # Secondary contributing factor


class EdgeType(Enum):
    """Types of edges in the RCA graph"""
    SUGGESTS = "suggests"            # Symptom suggests hypothesis
    REQUIRES = "requires"            # Hypothesis requires test
    CONFIRMS = "confirms"            # Test confirms finding
    REFUTES = "refutes"              # Test refutes hypothesis
    CAUSES = "causes"                # Finding causes symptom
    CONTRIBUTES_TO = "contributes_to"  # Factor contributes to symptom


@dataclass
class RCANode:
    """
    A node in the RCA graph representing a diagnostic element.

    Attributes:
        id: Unique identifier for the node
        type: The type of node (symptom, hypothesis, test, finding, root_cause)
        title: Human-readable title
        description: Detailed description
        metadata: Additional context (timestamps, metrics, agent info, etc.)
        confidence: Confidence score (0.0 to 1.0) for hypotheses and findings
        created_at: Timestamp when node was created
        updated_at: Timestamp when node was last updated
    """
    id: str
    type: NodeType
    title: str
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary representation"""
        return {
            'id': self.id,
            'type': self.type.value,
            'title': self.title,
            'description': self.description,
            'metadata': self.metadata,
            'confidence': self.confidence,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass
class RCAEdge:
    """
    An edge in the RCA graph representing a relationship between nodes.

    Attributes:
        source: ID of source node
        target: ID of target node
        type: The type of relationship
        weight: Strength of the relationship (0.0 to 1.0)
        metadata: Additional context about the relationship
        created_at: Timestamp when edge was created
    """
    source: str
    target: str
    type: EdgeType
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert edge to dictionary representation"""
        return {
            'source': self.source,
            'target': self.target,
            'type': self.type.value,
            'weight': self.weight,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
        }


class RCAGraph:
    """
    The main RCA graph structure that holds nodes and edges.

    This graph represents the entire diagnostic process, from initial symptoms
    through hypotheses, tests, findings, and root causes.
    """

    def __init__(self, incident_id: str):
        """
        Initialize a new RCA graph for an incident.

        Args:
            incident_id: Unique identifier for the incident
        """
        self.incident_id = incident_id
        self.nodes: Dict[str, RCANode] = {}
        self.edges: List[RCAEdge] = []
        self.created_at = datetime.utcnow()
        self.metadata: Dict[str, Any] = {}

    def add_node(self, node: RCANode) -> None:
        """
        Add a node to the graph.

        Args:
            node: The RCANode to add
        """
        self.nodes[node.id] = node

    def add_edge(self, edge: RCAEdge) -> None:
        """
        Add an edge to the graph.

        Args:
            edge: The RCAEdge to add

        Raises:
            ValueError: If source or target node doesn't exist
        """
        if edge.source not in self.nodes:
            raise ValueError(f"Source node {edge.source} not found in graph")
        if edge.target not in self.nodes:
            raise ValueError(f"Target node {edge.target} not found in graph")
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[RCANode]:
        """Get a node by ID"""
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> List[RCANode]:
        """Get all nodes of a specific type"""
        return [node for node in self.nodes.values() if node.type == node_type]

    def get_outgoing_edges(self, node_id: str) -> List[RCAEdge]:
        """Get all edges originating from a node"""
        return [edge for edge in self.edges if edge.source == node_id]

    def get_incoming_edges(self, node_id: str) -> List[RCAEdge]:
        """Get all edges pointing to a node"""
        return [edge for edge in self.edges if edge.target == node_id]

    def get_root_causes(self) -> List[RCANode]:
        """Get all nodes identified as root causes"""
        return self.get_nodes_by_type(NodeType.ROOT_CAUSE)

    def get_contributing_factors(self) -> List[RCANode]:
        """Get all nodes identified as contributing factors"""
        return self.get_nodes_by_type(NodeType.CONTRIBUTING_FACTOR)

    def traverse_from_symptom(self, symptom_id: str) -> List[str]:
        """
        Traverse the graph from a symptom to find connected root causes.

        Args:
            symptom_id: ID of the symptom node to start from

        Returns:
            List of node IDs in the causal chain
        """
        visited: Set[str] = set()
        path: List[str] = []

        def dfs(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)
            path.append(node_id)

            for edge in self.get_outgoing_edges(node_id):
                dfs(edge.target)

        dfs(symptom_id)
        return path

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the entire graph to a dictionary representation.

        Returns:
            Dictionary containing all graph data
        """
        return {
            'incident_id': self.incident_id,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata,
            'nodes': [node.to_dict() for node in self.nodes.values()],
            'edges': [edge.to_dict() for edge in self.edges],
        }

    def to_json(self, indent: int = 2) -> str:
        """
        Convert the graph to JSON string.

        Args:
            indent: Number of spaces for indentation

        Returns:
            JSON string representation of the graph
        """
        return json.dumps(self.to_dict(), indent=indent)

    def export_narrative(self) -> str:
        """
        Generate a human-readable narrative from the RCA graph.

        Returns:
            Markdown-formatted narrative describing the RCA process
        """
        narrative_parts = []

        narrative_parts.append(f"# Root Cause Analysis: {self.incident_id}\n")
        narrative_parts.append(f"**Analysis Started:** {self.created_at.isoformat()}\n")

        # Symptoms
        symptoms = self.get_nodes_by_type(NodeType.SYMPTOM)
        if symptoms:
            narrative_parts.append("\n## Observed Symptoms\n")
            for symptom in symptoms:
                narrative_parts.append(f"- **{symptom.title}**: {symptom.description}")

        # Root Causes
        root_causes = self.get_root_causes()
        if root_causes:
            narrative_parts.append("\n## Root Causes Identified\n")
            for rc in sorted(root_causes, key=lambda x: x.confidence, reverse=True):
                narrative_parts.append(
                    f"- **{rc.title}** (confidence: {rc.confidence:.2f})\n"
                    f"  {rc.description}"
                )

        # Contributing Factors
        factors = self.get_contributing_factors()
        if factors:
            narrative_parts.append("\n## Contributing Factors\n")
            for factor in factors:
                narrative_parts.append(f"- {factor.title}: {factor.description}")

        # Findings
        findings = self.get_nodes_by_type(NodeType.FINDING)
        if findings:
            narrative_parts.append("\n## Key Findings\n")
            for finding in findings:
                narrative_parts.append(f"- {finding.description}")

        return "\n".join(narrative_parts)
