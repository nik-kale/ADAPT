"""
Incident management API routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime
import logging

from ..models import RCAListItem
from ..auth import get_current_user, require_view_incidents, User
from core import get_graph_storage

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/incidents", response_model=List[RCAListItem])
async def list_incidents(
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    user: User = Depends(require_view_incidents),
):
    """
    List historical incidents.

    Returns a paginated list of incidents with summary information.
    """
    storage = get_graph_storage()
    if not storage:
        raise HTTPException(status_code=503, detail="Graph storage not configured")

    graphs = await storage.list_graphs(
        start_date=start_date, end_date=end_date, limit=limit
    )

    items = []
    for graph_meta in graphs:
        # Count root causes from graph if available
        root_causes_count = 0
        findings_count = 0

        # Load full graph to get counts (could be optimized with better storage)
        try:
            graph = await storage.load_graph(graph_meta["incident_id"])
            if graph:
                root_causes_count = len(graph.get_root_causes())
                findings_count = len(graph.get_nodes_by_type("finding"))
        except Exception as e:
            logger.warning(
                f"Could not load graph for {graph_meta['incident_id']}: {e}"
            )

        items.append(
            RCAListItem(
                incident_id=graph_meta["incident_id"],
                status="completed",
                created_at=datetime.fromisoformat(graph_meta["created_at"])
                if isinstance(graph_meta["created_at"], str)
                else graph_meta["created_at"],
                root_causes_count=root_causes_count,
                findings_count=findings_count,
            )
        )

    return items


@router.delete("/incidents/{incident_id}")
async def delete_incident(
    incident_id: str, user: User = Depends(get_current_user)
):
    """
    Delete an incident from storage.

    Requires admin permission.
    """
    from ..auth import require_admin

    # Check admin permission
    if not user.has_permission("admin"):
        raise HTTPException(
            status_code=403, detail="Admin permission required to delete incidents"
        )

    storage = get_graph_storage()
    if not storage:
        raise HTTPException(status_code=503, detail="Graph storage not configured")

    # For now, we don't have a delete method in storage
    # In production, you would implement this
    raise HTTPException(status_code=501, detail="Delete not implemented yet")
