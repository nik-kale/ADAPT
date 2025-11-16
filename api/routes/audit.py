"""
Audit Logging API Routes

Endpoints for querying audit logs and compliance reports.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from api.auth import User, require_admin, require_view_metrics
from core.audit import get_audit_logger, AuditEvent, AuditEventType, AuditLevel

router = APIRouter(prefix="/audit", tags=["Audit Logging"])


# Response Models

class AuditEventResponse(BaseModel):
    event_id: str
    event_type: str
    tenant_id: str
    user_id: Optional[str]
    action: str
    resource_id: Optional[str]
    result: str
    level: str
    timestamp: datetime
    ip_address: Optional[str]
    details: dict


class AuditSummaryResponse(BaseModel):
    total_events: int
    event_types: dict
    users: List[str]
    resources: List[str]
    date_range: dict


# Endpoints

@router.get("/events", response_model=List[AuditEventResponse])
async def list_audit_events(
    event_type: Optional[AuditEventType] = None,
    user_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    level: Optional[AuditLevel] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    user: User = Depends(require_admin)
):
    """
    List audit events with filtering.

    Requires admin role.
    """
    audit_logger = get_audit_logger()
    if not audit_logger:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit logging not enabled"
        )

    # Build filters
    filters = {}
    if event_type:
        filters['event_type'] = event_type
    if user_id:
        filters['user_id'] = user_id
    if resource_id:
        filters['resource_id'] = resource_id
    if level:
        filters['level'] = level

    # Query events (simplified - in production would query storage backend)
    events = []

    # Note: This is a simplified implementation
    # In production, would query from actual storage (file/elasticsearch/database)
    return events


@router.get("/events/{event_id}", response_model=AuditEventResponse)
async def get_audit_event(
    event_id: str,
    user: User = Depends(require_admin)
):
    """Get specific audit event by ID"""
    audit_logger = get_audit_logger()
    if not audit_logger:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit logging not enabled"
        )

    # In production, would retrieve from storage
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Audit event {event_id} not found"
    )


@router.get("/users/{user_id}/activity", response_model=List[AuditEventResponse])
async def get_user_activity(
    user_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    user: User = Depends(require_admin)
):
    """Get audit events for specific user"""
    return await list_audit_events(
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        user=user
    )


@router.get("/resources/{resource_id}/history", response_model=List[AuditEventResponse])
async def get_resource_history(
    resource_id: str,
    limit: int = Query(100, le=1000),
    user: User = Depends(require_admin)
):
    """Get audit history for specific resource"""
    return await list_audit_events(
        resource_id=resource_id,
        limit=limit,
        user=user
    )


@router.get("/security", response_model=List[AuditEventResponse])
async def get_security_events(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    user: User = Depends(require_admin)
):
    """Get security-related audit events"""
    # Security event types
    security_events = [
        AuditEventType.LOGIN_FAILED,
        AuditEventType.PERMISSION_DENIED,
        AuditEventType.QUOTA_EXCEEDED,
        AuditEventType.SUSPICIOUS_ACTIVITY,
        AuditEventType.TOKEN_REVOKED
    ]

    # Query for each type
    events = []
    for event_type in security_events:
        events.extend(await list_audit_events(
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
            limit=limit // len(security_events),
            user=user
        ))

    return events[:limit]


@router.get("/summary", response_model=AuditSummaryResponse)
async def get_audit_summary(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    user: User = Depends(require_admin)
):
    """Get audit log summary statistics"""
    audit_logger = get_audit_logger()
    if not audit_logger:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit logging not enabled"
        )

    # In production, would aggregate from storage
    return AuditSummaryResponse(
        total_events=0,
        event_types={},
        users=[],
        resources=[],
        date_range={
            'start': start_time.isoformat() if start_time else None,
            'end': end_time.isoformat() if end_time else None
        }
    )
