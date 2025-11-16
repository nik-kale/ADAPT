"""
Knowledge Base API Routes

Endpoints for querying historical RCA knowledge and getting recommendations.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from api.auth import User, require_run_rca
from core.knowledge_base import KnowledgeBase, KnowledgeEntry
from core.signal_normalizer import NormalizedSignal
from core.tenant import get_tenant_context
from core.audit import get_audit_logger, AuditEventType

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])

# Global knowledge base instance
_knowledge_base: Optional[KnowledgeBase] = None


async def get_knowledge_base() -> KnowledgeBase:
    """Get or initialize global knowledge base"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase()
        await _knowledge_base.initialize()
    return _knowledge_base


# Request/Response Models

class SimilarIncidentSearchRequest(BaseModel):
    query: str = Field(..., description="Query describing the incident")
    limit: int = Field(5, ge=1, le=20, description="Maximum results")
    min_similarity: float = Field(0.6, ge=0.0, le=1.0, description="Minimum similarity score")


class SimilarIncidentResponse(BaseModel):
    id: str
    incident_id: str
    incident_type: str
    similarity: float
    root_causes: List[str]
    symptoms: List[str]
    resolution_steps: List[str]
    timestamp: str


class RecommendationRequest(BaseModel):
    signals: List[Dict[str, Any]] = Field(..., description="Current incident signals")


class RecommendationResponse(BaseModel):
    recommendations: List[Dict[str, Any]]
    resolution_steps: List[Dict[str, Any]]
    similar_incidents: List[SimilarIncidentResponse]
    confidence: float


class KnowledgeStatsResponse(BaseModel):
    total_entries: int
    tenant_entries: int
    collection_name: str
    available: bool


# Endpoints

@router.post("/search", response_model=List[SimilarIncidentResponse])
async def search_similar_incidents(
    request: SimilarIncidentSearchRequest,
    user: User = Depends(require_run_rca)
):
    """
    Search for similar historical incidents using semantic search.

    Uses vector embeddings to find incidents with similar symptoms and patterns.
    Requires ChromaDB and sentence-transformers to be installed.
    """
    kb = await get_knowledge_base()
    tenant_id = get_tenant_context() or "default"

    if not kb._initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge base not available. Install: pip install chromadb sentence-transformers"
        )

    # Search for similar incidents
    similar = await kb.find_similar_incidents(
        query_text=request.query,
        tenant_id=tenant_id,
        limit=request.limit,
        min_similarity=request.min_similarity
    )

    # Audit log
    audit_logger = get_audit_logger()
    if audit_logger:
        await audit_logger.log_event(
            event_type=AuditEventType.INCIDENT_VIEWED,
            action="search_knowledge_base",
            resource_id="knowledge_base",
            result="success",
            details={
                'query_length': len(request.query),
                'results_found': len(similar),
                'min_similarity': request.min_similarity
            }
        )

    # Convert to response format
    return [
        SimilarIncidentResponse(
            id=item['id'],
            incident_id=item['incident_id'],
            incident_type=item['incident_type'],
            similarity=item['similarity'],
            root_causes=item['root_causes'],
            symptoms=item['symptoms'],
            resolution_steps=item['resolution_steps'],
            timestamp=item['timestamp']
        )
        for item in similar
    ]


@router.get("/incidents/{incident_id}/similar", response_model=List[SimilarIncidentResponse])
async def get_similar_to_incident(
    incident_id: str,
    limit: int = 5,
    min_similarity: float = 0.6,
    user: User = Depends(require_run_rca)
):
    """
    Get incidents similar to a specific incident.

    Finds historical incidents with similar patterns to the specified incident.
    """
    kb = await get_knowledge_base()
    tenant_id = get_tenant_context() or "default"

    if not kb._initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge base not available"
        )

    # Build query from incident ID
    query = f"Incident similar to {incident_id}"

    similar = await kb.find_similar_incidents(
        query_text=query,
        tenant_id=tenant_id,
        limit=limit,
        min_similarity=min_similarity
    )

    return [
        SimilarIncidentResponse(
            id=item['id'],
            incident_id=item['incident_id'],
            incident_type=item['incident_type'],
            similarity=item['similarity'],
            root_causes=item['root_causes'],
            symptoms=item['symptoms'],
            resolution_steps=item['resolution_steps'],
            timestamp=item['timestamp']
        )
        for item in similar
    ]


@router.post("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest,
    user: User = Depends(require_run_rca)
):
    """
    Get incident recommendations based on current signals.

    Analyzes current signals and returns:
    - Likely root causes based on similar past incidents
    - Recommended resolution steps
    - Most similar historical incidents
    - Overall confidence score
    """
    kb = await get_knowledge_base()
    tenant_id = get_tenant_context() or "default"

    if not kb._initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge base not available"
        )

    # Convert signal dicts to NormalizedSignal objects (simplified)
    # In production, would properly deserialize signals
    signals = []
    for sig_dict in request.signals:
        # Create mock signal for now
        class MockSignal:
            def __init__(self, data):
                self.title = data.get('title', 'Unknown')
                self.description = data.get('description', '')
                self.signal_type = data.get('signal_type', 'log')

        signals.append(MockSignal(sig_dict))

    # Get recommendations
    recommendations = await kb.get_incident_recommendations(
        current_signals=signals,
        tenant_id=tenant_id
    )

    # Audit log
    audit_logger = get_audit_logger()
    if audit_logger:
        await audit_logger.log_event(
            event_type=AuditEventType.INCIDENT_VIEWED,
            action="get_recommendations",
            resource_id="knowledge_base",
            result="success",
            details={
                'signal_count': len(signals),
                'recommendations_count': len(recommendations.get('recommendations', [])),
                'confidence': recommendations.get('confidence', 0.0)
            }
        )

    # Convert similar incidents to response format
    similar_incidents = []
    for item in recommendations.get('similar_incidents', []):
        similar_incidents.append(SimilarIncidentResponse(
            id=item['id'],
            incident_id=item['incident_id'],
            incident_type=item['incident_type'],
            similarity=item['similarity'],
            root_causes=item['root_causes'],
            symptoms=item['symptoms'],
            resolution_steps=item['resolution_steps'],
            timestamp=item['timestamp']
        ))

    return RecommendationResponse(
        recommendations=recommendations.get('recommendations', []),
        resolution_steps=recommendations.get('resolution_steps', []),
        similar_incidents=similar_incidents,
        confidence=recommendations.get('confidence', 0.0)
    )


@router.get("/stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats(user: User = Depends(require_run_rca)):
    """Get knowledge base statistics"""
    kb = await get_knowledge_base()
    tenant_id = get_tenant_context() or "default"

    if not kb._initialized:
        return KnowledgeStatsResponse(
            total_entries=0,
            tenant_entries=0,
            collection_name="",
            available=False
        )

    stats = await kb.get_statistics(tenant_id=tenant_id)

    return KnowledgeStatsResponse(
        total_entries=stats.get('total_entries', 0),
        tenant_entries=stats.get('tenant_entries', 0),
        collection_name=stats.get('collection_name', ''),
        available=True
    )
