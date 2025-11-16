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
    offset: int = Query(0, ge=0, description="Number of results to skip (v4.0 pagination)"),
    user: User = Depends(require_view_incidents),
):
    """
    List historical incidents (v4.0 enhanced with pagination).

    Returns a paginated list of incidents with summary information.

    v4.0 Performance Enhancement: Uses optimized query to get counts
    without N+1 database calls (10-100x faster for large datasets).
    """
    storage = get_graph_storage()
    if not storage:
        raise HTTPException(status_code=503, detail="Graph storage not configured")

    # v4.0: Pass offset for pagination
    graphs = await storage.list_graphs(
        start_date=start_date, end_date=end_date, limit=limit, offset=offset
    )

    items = []
    for graph_meta in graphs:
        # v4.0: Get counts from metadata (N+1 query fix)
        # No longer need to load full graph - counts are in metadata
        root_causes_count = graph_meta.get("root_causes_count", 0)
        findings_count = graph_meta.get("findings_count", 0)

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
    Delete an incident from storage (v4.0 product enhancement).

    Requires admin permission. Deletion is permanent and cannot be undone.
    """
    from ..auth import Permission

    # Check admin permission
    if not user.has_permission(Permission.ADMIN):
        raise HTTPException(
            status_code=403, detail="Admin permission required to delete incidents"
        )

    storage = get_graph_storage()
    if not storage:
        raise HTTPException(status_code=503, detail="Graph storage not configured")

    # v4.0: Implemented delete functionality
    success = await storage.delete_graph(incident_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    # v4.0: Audit the deletion
    try:
        from core.audit import get_audit_logger, AuditEventType

        audit_logger = get_audit_logger()
        if audit_logger:
            await audit_logger.log_event(
                event_type=AuditEventType.INCIDENT_DELETED,
                action="delete_incident",
                resource_id=incident_id,
                resource_type="incident",
                user_id=user.username,
                tenant_id=user.tenant_id,
                result="success",
                details={
                    "incident_id": incident_id,
                    "deleted_by": user.username,
                },
            )
    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not log audit event: {e}")

    return {"deleted": True, "incident_id": incident_id}
