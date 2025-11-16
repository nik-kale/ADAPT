"""
Knowledge Base with RAG and Vector Search

Stores and retrieves historical RCA findings using semantic search.
Enables learning from past incidents to improve analysis quality.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeEntry:
    """Entry in the knowledge base"""
    id: str
    incident_id: str
    incident_type: str
    root_causes: List[str]
    symptoms: List[str]
    resolution_steps: List[str]
    context: Dict[str, Any]
    timestamp: datetime
    tenant_id: str = "default"

    def to_text(self) -> str:
        """Convert entry to searchable text"""
        return f"""
Incident Type: {self.incident_type}
Symptoms: {', '.join(self.symptoms)}
Root Causes: {', '.join(self.root_causes)}
Resolution: {', '.join(self.resolution_steps)}
Context: {json.dumps(self.context)}
        """.strip()


class KnowledgeBase:
    """
    RAG-enabled knowledge base for storing and retrieving RCA insights.

    Features:
    - Vector embeddings for semantic search
    - Historical incident storage
    - Similar incident retrieval
    - Learning from past RCAs
    """

    def __init__(self, collection_name: str = "rca_knowledge", persist_directory: str = "./data/knowledge"):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.collection = None
        self.embedding_model = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the knowledge base"""
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            # Initialize ChromaDB
            self.client = chromadb.PersistentClient(path=self.persist_directory)

            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "ADAPT RCA Knowledge Base"}
            )

            # Initialize embedding model
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

            logger.info(f"Knowledge base initialized with {self.collection.count()} entries")
            self._initialized = True
            return True

        except ImportError:
            logger.warning(
                "Knowledge base dependencies not installed. "
                "Install with: pip install chromadb sentence-transformers"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to initialize knowledge base: {e}")
            return False

    async def add_rca_result(self, rca_context, tenant_id: str = "default") -> str:
        """
        Add RCA result to knowledge base.

        Args:
            rca_context: OrchestrationContext from RCA
            tenant_id: Tenant identifier

        Returns:
            Entry ID
        """
        if not self._initialized:
            logger.warning("Knowledge base not initialized")
            return ""

        try:
            # Extract key information from RCA context
            root_causes = [
                cause.title for cause in rca_context.graph.get_root_causes()
            ]

            # Collect symptoms from signals
            symptoms = []
            for signal in rca_context.signals[:10]:  # Top 10 signals
                if hasattr(signal, 'title'):
                    symptoms.append(signal.title)

            # Extract resolution steps if available
            resolution_steps = []
            remediation_result = rca_context.agent_results.get('remediation_planner', {})
            if isinstance(remediation_result, dict) and 'playbook' in remediation_result:
                playbook = remediation_result['playbook']
                if hasattr(playbook, 'steps'):
                    resolution_steps = [step.description for step in playbook.steps]

            # Determine incident type
            incident_type = self._classify_incident(rca_context)

            # Create knowledge entry
            entry = KnowledgeEntry(
                id=f"kb_{rca_context.incident_id}_{datetime.utcnow().timestamp()}",
                incident_id=rca_context.incident_id,
                incident_type=incident_type,
                root_causes=root_causes,
                symptoms=symptoms,
                resolution_steps=resolution_steps,
                context={
                    'execution_mode': rca_context.config.execution_mode,
                    'agent_count': len(rca_context.agent_results),
                    'confidence_scores': {
                        name: result.get('confidence', 0.0)
                        for name, result in rca_context.agent_results.items()
                        if isinstance(result, dict)
                    }
                },
                timestamp=datetime.utcnow(),
                tenant_id=tenant_id
            )

            # Generate embedding
            text = entry.to_text()
            embedding = self.embedding_model.encode(text).tolist()

            # Store in vector database
            self.collection.add(
                ids=[entry.id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[{
                    'incident_id': entry.incident_id,
                    'incident_type': entry.incident_type,
                    'tenant_id': entry.tenant_id,
                    'timestamp': entry.timestamp.isoformat(),
                    'root_causes': json.dumps(entry.root_causes),
                    'symptoms': json.dumps(entry.symptoms),
                    'resolution_steps': json.dumps(entry.resolution_steps)
                }]
            )

            logger.info(f"Added RCA result to knowledge base: {entry.id}")
            return entry.id

        except Exception as e:
            logger.error(f"Failed to add RCA result to knowledge base: {e}")
            return ""

    async def find_similar_incidents(
        self,
        query_text: str,
        tenant_id: str = "default",
        limit: int = 5,
        min_similarity: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Find similar historical incidents using semantic search.

        Args:
            query_text: Query describing the current incident
            tenant_id: Tenant to search within
            limit: Maximum number of results
            min_similarity: Minimum similarity score (0-1)

        Returns:
            List of similar incidents with metadata
        """
        if not self._initialized:
            return []

        try:
            # Generate embedding for query
            query_embedding = self.embedding_model.encode(query_text).tolist()

            # Search in vector database
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where={"tenant_id": tenant_id}
            )

            similar_incidents = []

            if results['ids'] and len(results['ids'][0]) > 0:
                for i, incident_id in enumerate(results['ids'][0]):
                    # Calculate similarity (distance to similarity conversion)
                    distance = results['distances'][0][i] if 'distances' in results else 0.0
                    similarity = 1.0 / (1.0 + distance)  # Convert distance to similarity

                    if similarity >= min_similarity:
                        metadata = results['metadatas'][0][i]

                        similar_incidents.append({
                            'id': incident_id,
                            'similarity': similarity,
                            'incident_id': metadata.get('incident_id'),
                            'incident_type': metadata.get('incident_type'),
                            'root_causes': json.loads(metadata.get('root_causes', '[]')),
                            'symptoms': json.loads(metadata.get('symptoms', '[]')),
                            'resolution_steps': json.loads(metadata.get('resolution_steps', '[]')),
                            'timestamp': metadata.get('timestamp')
                        })

            logger.info(f"Found {len(similar_incidents)} similar incidents (min_similarity={min_similarity})")
            return similar_incidents

        except Exception as e:
            logger.error(f"Failed to search knowledge base: {e}")
            return []

    async def get_incident_recommendations(
        self,
        current_signals: List[Any],
        tenant_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Get recommendations based on current incident signals.

        Args:
            current_signals: Current incident signals
            tenant_id: Tenant identifier

        Returns:
            Recommendations including likely root causes and resolution steps
        """
        if not self._initialized:
            return {'recommendations': [], 'confidence': 0.0}

        try:
            # Build query from signals
            signal_descriptions = []
            for signal in current_signals[:20]:  # Top 20 signals
                if hasattr(signal, 'title'):
                    signal_descriptions.append(signal.title)
                elif hasattr(signal, 'description'):
                    signal_descriptions.append(signal.description)

            query_text = "Incident with symptoms: " + ", ".join(signal_descriptions)

            # Find similar incidents
            similar = await self.find_similar_incidents(
                query_text=query_text,
                tenant_id=tenant_id,
                limit=10,
                min_similarity=0.5
            )

            if not similar:
                return {'recommendations': [], 'confidence': 0.0}

            # Aggregate recommendations from similar incidents
            root_cause_votes = {}
            resolution_votes = {}

            for incident in similar:
                weight = incident['similarity']

                # Vote for root causes
                for cause in incident['root_causes']:
                    root_cause_votes[cause] = root_cause_votes.get(cause, 0.0) + weight

                # Vote for resolution steps
                for step in incident['resolution_steps']:
                    resolution_votes[step] = resolution_votes.get(step, 0.0) + weight

            # Sort by votes
            recommended_causes = sorted(
                root_cause_votes.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]

            recommended_resolutions = sorted(
                resolution_votes.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]

            # Calculate overall confidence
            avg_similarity = sum(inc['similarity'] for inc in similar) / len(similar)

            return {
                'recommendations': [
                    {
                        'root_cause': cause,
                        'confidence': score / len(similar),
                        'supporting_incidents': len(similar)
                    }
                    for cause, score in recommended_causes
                ],
                'resolution_steps': [
                    {
                        'step': step,
                        'confidence': score / len(similar)
                    }
                    for step, score in recommended_resolutions
                ],
                'similar_incidents': similar[:3],  # Top 3 most similar
                'confidence': avg_similarity
            }

        except Exception as e:
            logger.error(f"Failed to get recommendations: {e}")
            return {'recommendations': [], 'confidence': 0.0}

    def _classify_incident(self, rca_context) -> str:
        """Classify incident type based on RCA context"""
        # Simple classification based on signals
        error_count = 0
        metric_anomaly_count = 0
        config_change_count = 0

        for signal in rca_context.signals:
            if hasattr(signal, 'signal_type'):
                signal_type = str(signal.signal_type).lower()
                if 'log' in signal_type:
                    if hasattr(signal, 'severity') and signal.severity in ['high', 'critical']:
                        error_count += 1
                elif 'metric' in signal_type:
                    metric_anomaly_count += 1
                elif 'config' in signal_type:
                    config_change_count += 1

        # Classify based on predominant signal type
        if config_change_count > 0:
            return "configuration_change"
        elif error_count > metric_anomaly_count:
            return "application_error"
        elif metric_anomaly_count > 0:
            return "performance_degradation"
        else:
            return "unknown"

    async def get_statistics(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        if not self._initialized:
            return {}

        try:
            total_count = self.collection.count()

            # Get tenant-specific count if specified
            tenant_count = total_count
            if tenant_id:
                result = self.collection.get(where={"tenant_id": tenant_id})
                tenant_count = len(result['ids'])

            return {
                'total_entries': total_count,
                'tenant_entries': tenant_count,
                'collection_name': self.collection_name,
                'persist_directory': self.persist_directory
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}


class RAGEnhancedOrchestrator:
    """
    Orchestrator enhanced with knowledge base for learning from past incidents.
    """

    def __init__(self, base_orchestrator, knowledge_base: KnowledgeBase):
        self.base_orchestrator = base_orchestrator
        self.knowledge_base = knowledge_base

    async def run_rca(self, incident_id: str, signals: List[Any], **kwargs):
        """
        Run RCA with knowledge base enhancement.

        First retrieves similar historical incidents, then runs RCA,
        then stores results for future learning.
        """
        from core.tenant import get_tenant_context

        tenant_id = get_tenant_context() or "default"

        # Get recommendations from knowledge base
        recommendations = await self.knowledge_base.get_incident_recommendations(
            current_signals=signals,
            tenant_id=tenant_id
        )

        logger.info(
            f"Knowledge base found {len(recommendations.get('recommendations', []))} "
            f"recommendations with confidence {recommendations.get('confidence', 0.0):.2f}"
        )

        # Add recommendations to kwargs for agents to use
        kwargs['kb_recommendations'] = recommendations

        # Run base RCA
        context = await self.base_orchestrator.run_rca(
            incident_id=incident_id,
            signals=signals,
            **kwargs
        )

        # Store results in knowledge base
        await self.knowledge_base.add_rca_result(context, tenant_id=tenant_id)

        # Add knowledge base insights to context
        context.metadata['kb_recommendations'] = recommendations
        context.metadata['kb_enhanced'] = True

        return context
