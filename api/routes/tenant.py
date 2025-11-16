"""
Tenant Management API Routes

Endpoints for managing multi-tenancy in ADAPT.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from api.auth import User, require_admin
from core.tenant import TenantConfig, TenantManager, get_tenant_context
from core.audit import get_audit_logger, AuditEventType

router = APIRouter(prefix="/tenants", tags=["Tenant Management"])

# Initialize tenant manager
_tenant_manager: TenantManager = None


def get_tenant_manager() -> TenantManager:
    """Get global tenant manager"""
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager


# Request/Response Models

class TenantCreateRequest(BaseModel):
    tenant_id: str = Field(..., description="Unique tenant identifier")
    name: str = Field(..., description="Tenant display name")
    max_concurrent_rca: int = Field(10, description="Maximum concurrent RCA operations")
    max_storage_gb: int = Field(100, description="Maximum storage in GB")
    custom_config: Dict[str, Any] = Field(default_factory=dict, description="Custom configuration")


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    enabled: bool
    max_concurrent_rca: int
    max_storage_gb: int
    created_at: datetime
    custom_config: Dict[str, Any]


class TenantUsageResponse(BaseModel):
    tenant_id: str
    total_rcas: int
    active_rcas: int
    storage_used_gb: float
    last_rca: str | None


class TenantQuotaResponse(BaseModel):
    tenant_id: str
    concurrent_rca_available: bool
    concurrent_rca_used: int
    concurrent_rca_limit: int
    storage_available: bool
    storage_used_gb: float
    storage_limit_gb: int


# Endpoints

@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreateRequest,
    user: User = Depends(require_admin)
):
    """Create a new tenant"""
    manager = get_tenant_manager()

    # Check if tenant already exists
    existing = manager.get_tenant_config(request.tenant_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant {request.tenant_id} already exists"
        )

    # Create tenant config
    config = TenantConfig(
        tenant_id=request.tenant_id,
        name=request.name,
        max_concurrent_rca=request.max_concurrent_rca,
        max_storage_gb=request.max_storage_gb,
        custom_config=request.custom_config
    )

    # Register tenant
    manager.register_tenant(config)

    # Audit log
    audit_logger = get_audit_logger()
    if audit_logger:
        await audit_logger.log_event(
            event_type=AuditEventType.TENANT_CREATED,
            action="create_tenant",
            resource_id=request.tenant_id,
            result="success",
            details={'name': request.name}
        )

    return TenantResponse(
        tenant_id=config.tenant_id,
        name=config.name,
        enabled=config.enabled,
        max_concurrent_rca=config.max_concurrent_rca,
        max_storage_gb=config.max_storage_gb,
        created_at=config.created_at,
        custom_config=config.custom_config
    )


@router.get("/", response_model=List[TenantResponse])
async def list_tenants(user: User = Depends(require_admin)):
    """List all tenants"""
    manager = get_tenant_manager()

    tenants = []
    for tenant_id, config in manager.tenants.items():
        tenants.append(TenantResponse(
            tenant_id=config.tenant_id,
            name=config.name,
            enabled=config.enabled,
            max_concurrent_rca=config.max_concurrent_rca,
            max_storage_gb=config.max_storage_gb,
            created_at=config.created_at,
            custom_config=config.custom_config
        ))

    return tenants


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str, user: User = Depends(require_admin)):
    """Get tenant details"""
    manager = get_tenant_manager()

    config = manager.get_tenant_config(tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )

    return TenantResponse(
        tenant_id=config.tenant_id,
        name=config.name,
        enabled=config.enabled,
        max_concurrent_rca=config.max_concurrent_rca,
        max_storage_gb=config.max_storage_gb,
        created_at=config.created_at,
        custom_config=config.custom_config
    )


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    request: Dict[str, Any],
    user: User = Depends(require_admin)
):
    """Update tenant configuration"""
    manager = get_tenant_manager()

    config = manager.get_tenant_config(tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )

    # Update fields
    if 'name' in request:
        config.name = request['name']
    if 'enabled' in request:
        config.enabled = request['enabled']
    if 'max_concurrent_rca' in request:
        config.max_concurrent_rca = request['max_concurrent_rca']
    if 'max_storage_gb' in request:
        config.max_storage_gb = request['max_storage_gb']
    if 'custom_config' in request:
        config.custom_config.update(request['custom_config'])

    # Audit log
    audit_logger = get_audit_logger()
    if audit_logger:
        await audit_logger.log_event(
            event_type=AuditEventType.TENANT_UPDATED,
            action="update_tenant",
            resource_id=tenant_id,
            result="success",
            details={'changes': request}
        )

    return TenantResponse(
        tenant_id=config.tenant_id,
        name=config.name,
        enabled=config.enabled,
        max_concurrent_rca=config.max_concurrent_rca,
        max_storage_gb=config.max_storage_gb,
        created_at=config.created_at,
        custom_config=config.custom_config
    )


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_tenant(tenant_id: str, user: User = Depends(require_admin)):
    """Disable a tenant"""
    manager = get_tenant_manager()

    config = manager.get_tenant_config(tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )

    config.enabled = False

    # Audit log
    audit_logger = get_audit_logger()
    if audit_logger:
        await audit_logger.log_event(
            event_type=AuditEventType.TENANT_DISABLED,
            action="disable_tenant",
            resource_id=tenant_id,
            result="success"
        )

    return None


@router.get("/{tenant_id}/usage", response_model=TenantUsageResponse)
async def get_tenant_usage(tenant_id: str, user: User = Depends(require_admin)):
    """Get tenant usage statistics"""
    manager = get_tenant_manager()

    config = manager.get_tenant_config(tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )

    stats = manager.get_usage_stats(tenant_id)

    return TenantUsageResponse(
        tenant_id=tenant_id,
        total_rcas=stats.get('total_rcas', 0),
        active_rcas=stats.get('active_rcas', 0),
        storage_used_gb=stats.get('storage_used_gb', 0.0),
        last_rca=stats.get('last_rca')
    )


@router.get("/{tenant_id}/quota", response_model=TenantQuotaResponse)
async def check_tenant_quota(tenant_id: str, user: User = Depends(require_admin)):
    """Check tenant quota status"""
    manager = get_tenant_manager()

    config = manager.get_tenant_config(tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found"
        )

    stats = manager.get_usage_stats(tenant_id)

    concurrent_available = manager.check_quota(tenant_id, 'concurrent_rca')
    storage_available = manager.check_quota(tenant_id, 'storage')

    return TenantQuotaResponse(
        tenant_id=tenant_id,
        concurrent_rca_available=concurrent_available,
        concurrent_rca_used=stats.get('active_rcas', 0),
        concurrent_rca_limit=config.max_concurrent_rca,
        storage_available=storage_available,
        storage_used_gb=stats.get('storage_used_gb', 0.0),
        storage_limit_gb=config.max_storage_gb
    )
