"""
Graph storage backends for persisting RCA graphs.

Supports Neo4j and other graph databases for long-term storage,
querying, and pattern matching across historical incidents.
"""

from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
import logging
from datetime import datetime

from .rca_graph import RCAGraph, RCANode, RCAEdge, NodeType, EdgeType

logger = logging.getLogger(__name__)


class GraphStorage(ABC):
    """Abstract interface for graph persistence"""

    @abstractmethod
    async def save_graph(self, graph: RCAGraph) -> str:
        """
        Save an RCA graph.

        Args:
            graph: The RCA graph to save

        Returns:
            Graph ID or incident ID
        """
        pass

    @abstractmethod
    async def load_graph(self, graph_id: str) -> Optional[RCAGraph]:
        """
        Load an RCA graph by ID.

        Args:
            graph_id: The graph/incident ID

        Returns:
            RCAGraph instance or None if not found
        """
        pass

    @abstractmethod
    async def query_similar_graphs(
        self,
        graph: RCAGraph,
        limit: int = 10
    ) -> List[RCAGraph]:
        """
        Find similar historical graphs.

        Args:
            graph: Reference graph to find similar incidents
            limit: Maximum number of results

        Returns:
            List of similar RCA graphs
        """
        pass

    @abstractmethod
    async def list_graphs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List stored graphs with metadata.

        Args:
            start_date: Filter graphs created after this date
            end_date: Filter graphs created before this date
            limit: Maximum number of results

        Returns:
            List of graph metadata dictionaries
        """
        pass


class Neo4jGraphStorage(GraphStorage):
    """
    Neo4j graph database storage.

    Requires: pip install neo4j
    """

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j storage.

        Args:
            uri: Neo4j connection URI
            user: Database username
            password: Database password

        Raises:
            ImportError: If neo4j is not installed
        """
        try:
            from neo4j import AsyncGraphDatabase
        except ImportError:
            raise ImportError("Install neo4j: pip install neo4j")

        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Connected to Neo4j at {uri}")

    async def save_graph(self, graph: RCAGraph) -> str:
        """Save RCA graph to Neo4j"""

        async with self.driver.session() as session:
            # Create incident node
            await session.run(
                """
                MERGE (i:Incident {id: $incident_id})
                SET i.created_at = $created_at,
                    i.updated_at = $updated_at
                """,
                incident_id=graph.incident_id,
                created_at=graph.created_at.isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )

            # Create RCA nodes
            for node in graph.nodes.values():
                await session.run(
                    """
                    MATCH (i:Incident {id: $incident_id})
                    MERGE (n:RCANode {id: $node_id, incident_id: $incident_id})
                    SET n.type = $type,
                        n.title = $title,
                        n.description = $description,
                        n.confidence = $confidence,
                        n.created_at = $created_at
                    MERGE (i)-[:HAS_NODE]->(n)
                    """,
                    incident_id=graph.incident_id,
                    node_id=node.id,
                    type=node.type.value,
                    title=node.title,
                    description=node.description,
                    confidence=node.confidence,
                    created_at=node.created_at.isoformat()
                )

            # Create edges
            for edge in graph.edges:
                await session.run(
                    """
                    MATCH (s:RCANode {id: $source, incident_id: $incident_id})
                    MATCH (t:RCANode {id: $target, incident_id: $incident_id})
                    MERGE (s)-[r:RELATES_TO {
                        type: $type,
                        incident_id: $incident_id
                    }]->(t)
                    SET r.weight = $weight,
                        r.created_at = $created_at
                    """,
                    incident_id=graph.incident_id,
                    source=edge.source,
                    target=edge.target,
                    type=edge.type.value,
                    weight=edge.weight,
                    created_at=edge.created_at.isoformat()
                )

        logger.info(f"Saved graph for incident: {graph.incident_id}")
        return graph.incident_id

    async def load_graph(self, graph_id: str) -> Optional[RCAGraph]:
        """Load RCA graph from Neo4j"""

        async with self.driver.session() as session:
            # Check if incident exists
            result = await session.run(
                """
                MATCH (i:Incident {id: $incident_id})
                RETURN i.created_at as created_at
                """,
                incident_id=graph_id
            )

            record = await result.single()
            if not record:
                return None

            # Create graph
            graph = RCAGraph(incident_id=graph_id)
            graph.created_at = datetime.fromisoformat(record['created_at'])

            # Load nodes
            nodes_result = await session.run(
                """
                MATCH (i:Incident {id: $incident_id})-[:HAS_NODE]->(n:RCANode)
                RETURN n
                """,
                incident_id=graph_id
            )

            async for record in nodes_result:
                node_data = record['n']
                node = RCANode(
                    id=node_data['id'],
                    type=NodeType(node_data['type']),
                    title=node_data['title'],
                    description=node_data['description'],
                    confidence=node_data['confidence'],
                    created_at=datetime.fromisoformat(node_data['created_at'])
                )
                graph.add_node(node)

            # Load edges
            edges_result = await session.run(
                """
                MATCH (s:RCANode)-[r:RELATES_TO {incident_id: $incident_id}]->(t:RCANode)
                WHERE s.incident_id = $incident_id AND t.incident_id = $incident_id
                RETURN s.id as source, t.id as target, r.type as type,
                       r.weight as weight, r.created_at as created_at
                """,
                incident_id=graph_id
            )

            async for record in edges_result:
                edge = RCAEdge(
                    source=record['source'],
                    target=record['target'],
                    type=EdgeType(record['type']),
                    weight=record['weight'],
                    created_at=datetime.fromisoformat(record['created_at'])
                )
                graph.add_edge(edge)

        logger.info(f"Loaded graph for incident: {graph_id}")
        return graph

    async def query_similar_graphs(
        self,
        graph: RCAGraph,
        limit: int = 10
    ) -> List[RCAGraph]:
        """
        Find similar incidents using graph similarity.

        Uses node type similarity and common patterns.
        """

        async with self.driver.session() as session:
            # Get node type distribution of input graph
            node_types = {}
            for node in graph.nodes.values():
                node_types[node.type.value] = node_types.get(node.type.value, 0) + 1

            # Find incidents with similar node type distributions
            result = await session.run(
                """
                MATCH (i:Incident)-[:HAS_NODE]->(n:RCANode)
                WHERE i.id <> $current_incident_id
                WITH i, n.type as node_type, count(*) as count
                WITH i, collect({type: node_type, count: count}) as distribution
                RETURN i.id as incident_id, distribution
                LIMIT $limit
                """,
                current_incident_id=graph.incident_id,
                limit=limit * 2  # Get more candidates for scoring
            )

            # Score and load top similar graphs
            similar_graphs = []

            async for record in result:
                # Calculate similarity score (simple Jaccard for now)
                incident_id = record['incident_id']

                # Load the graph
                similar_graph = await self.load_graph(incident_id)
                if similar_graph:
                    similar_graphs.append(similar_graph)

                if len(similar_graphs) >= limit:
                    break

        return similar_graphs

    async def list_graphs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List stored graphs with metadata"""

        async with self.driver.session() as session:
            query = """
            MATCH (i:Incident)
            WHERE 1=1
            """

            params = {'limit': limit}

            if start_date:
                query += " AND i.created_at >= $start_date"
                params['start_date'] = start_date.isoformat()

            if end_date:
                query += " AND i.created_at <= $end_date"
                params['end_date'] = end_date.isoformat()

            query += """
            OPTIONAL MATCH (i)-[:HAS_NODE]->(n:RCANode)
            WITH i, count(n) as node_count
            RETURN i.id as incident_id,
                   i.created_at as created_at,
                   i.updated_at as updated_at,
                   node_count
            ORDER BY i.created_at DESC
            LIMIT $limit
            """

            result = await session.run(query, **params)

            graphs = []
            async for record in result:
                graphs.append({
                    'incident_id': record['incident_id'],
                    'created_at': record['created_at'],
                    'updated_at': record['updated_at'],
                    'node_count': record['node_count']
                })

        return graphs

    async def close(self):
        """Close database connection"""
        await self.driver.close()


# Global graph storage instance
_graph_storage: Optional[GraphStorage] = None


def set_graph_storage(storage: GraphStorage):
    """
    Set the global graph storage backend.

    Args:
        storage: Graph storage instance to use
    """
    global _graph_storage
    _graph_storage = storage


def get_graph_storage() -> Optional[GraphStorage]:
    """
    Get the global graph storage backend.

    Returns:
        Graph storage instance or None if not configured
    """
    return _graph_storage
