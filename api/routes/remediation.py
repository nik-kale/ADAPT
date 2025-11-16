"""
Auto-Remediation API Routes

Endpoints for managing automated remediation plans and execution.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from api.auth import User, require_run_rca, require_admin
from core.auto_remediation import (
    AutoRemediationEngine,
    RemediationPlan,
    RemediationAction,
    RemediationStatus,
    RemediationResult,
    ActionRisk,
    get_remediation_engine
)
from core.tenant import get_tenant_context
from core.audit import get_audit_logger, AuditEventType

router = APIRouter(prefix="/remediation", tags=["Auto-Remediation"])


# Request/Response Models

class RemediationActionModel(BaseModel):
    action_id: str
    action_type: str
    description: str
    risk_level: ActionRisk
    target_service: str
    command: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timeout: int = 300
    rollback_command: Optional[str] = None


class RemediationPlanRequest(BaseModel):
    incident_id: str
    actions: List[RemediationActionModel]
    approval_required: bool = True
    max_risk_level: ActionRisk = ActionRisk.MEDIUM


class RemediationPlanResponse(BaseModel):
    plan_id: str
    incident_id: str
    status: RemediationStatus
    approval_required: bool
    action_count: int
    max_risk_level: ActionRisk
    created_at: datetime
    created_by: str


class RemediationResultResponse(BaseModel):
    plan_id: str
    status: RemediationStatus
    executed_actions: List[str]
    failed_actions: List[str]
    rollback_performed: bool
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    error_message: Optional[str]
    logs: List[str]


# Endpoints

@router.post("/plans", response_model=RemediationPlanResponse, status_code=status.HTTP_201_CREATED)
async def submit_remediation_plan(
    request: RemediationPlanRequest,
    user: User = Depends(require_run_rca)
):
    """Submit a remediation plan for approval/execution"""
    engine = get_remediation_engine()
    tenant_id = get_tenant_context() or "default"

    # Convert actions
    actions = [
        RemediationAction(
            action_id=action.action_id,
            action_type=action.action_type,
            description=action.description,
            risk_level=action.risk_level,
            target_service=action.target_service,
            command=action.command,
            parameters=action.parameters,
            timeout=action.timeout,
            rollback_command=action.rollback_command
        )
        for action in request.actions
    ]

    # Create plan
    plan = RemediationPlan(
        plan_id=f"plan_{datetime.utcnow().timestamp()}",
        incident_id=request.incident_id,
        actions=actions,
        created_at=datetime.utcnow(),
        created_by=user.username,
        tenant_id=tenant_id,
        approval_required=request.approval_required,
        max_risk_level=request.max_risk_level
    )

    # Submit plan
    plan_id = await engine.submit_plan(plan)

    # Audit log
    audit_logger = get_audit_logger()
    if audit_logger:
        await audit_logger.log_event(
            event_type=AuditEventType.REMEDIATION_PLAN_CREATED,
            action="submit_remediation_plan",
            resource_id=plan_id,
            result="success",
            details={
                'incident_id': request.incident_id,
                'action_count': len(actions),
                'max_risk_level': request.max_risk_level,
                'auto_approved': plan.status == RemediationStatus.APPROVED
            }
        )

    return RemediationPlanResponse(
        plan_id=plan_id,
        incident_id=plan.incident_id,
        status=plan.status,
        approval_required=plan.approval_required,
        action_count=len(plan.actions),
        max_risk_level=plan.max_risk_level,
        created_at=plan.created_at,
        created_by=plan.created_by
    )


@router.get("/plans", response_model=List[RemediationPlanResponse])
async def list_remediation_plans(
    status_filter: Optional[RemediationStatus] = None,
    user: User = Depends(require_run_rca)
):
    """List remediation plans"""
    engine = get_remediation_engine()
    tenant_id = get_tenant_context() or "default"

    plans = []

    # Get plans from all storage locations
    for plan_dict in [engine.pending_plans, engine.executing_plans]:
        for plan_id, plan in plan_dict.items():
            # Filter by tenant
            if plan.tenant_id != tenant_id:
                continue

            # Filter by status if specified
            if status_filter and plan.status != status_filter:
                continue

            plans.append(RemediationPlanResponse(
                plan_id=plan.plan_id,
                incident_id=plan.incident_id,
                status=plan.status,
                approval_required=plan.approval_required,
                action_count=len(plan.actions),
                max_risk_level=plan.max_risk_level,
                created_at=plan.created_at,
                created_by=plan.created_by
            ))

    # Add completed plans
    for plan_id, result in engine.completed_plans.items():
        if status_filter and result.status != status_filter:
            continue

        # Need to get original plan details from metadata
        plans.append(RemediationPlanResponse(
            plan_id=plan_id,
            incident_id=result.metadata.get('incident_id', 'unknown'),
            status=result.status,
            approval_required=True,
            action_count=result.metadata.get('total_actions', 0),
            max_risk_level=ActionRisk.MEDIUM,  # Not stored in result
            created_at=result.start_time,
            created_by="unknown"  # Not stored in result
        ))

    return plans


@router.get("/plans/{plan_id}", response_model=RemediationPlanResponse)
async def get_remediation_plan(
    plan_id: str,
    user: User = Depends(require_run_rca)
):
    """Get remediation plan details"""
    engine = get_remediation_engine()
    tenant_id = get_tenant_context() or "default"

    # Search for plan
    plan = None
    if plan_id in engine.pending_plans:
        plan = engine.pending_plans[plan_id]
    elif plan_id in engine.executing_plans:
        plan = engine.executing_plans[plan_id]

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan {plan_id} not found"
        )

    # Check tenant access
    if plan.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this remediation plan"
        )

    return RemediationPlanResponse(
        plan_id=plan.plan_id,
        incident_id=plan.incident_id,
        status=plan.status,
        approval_required=plan.approval_required,
        action_count=len(plan.actions),
        max_risk_level=plan.max_risk_level,
        created_at=plan.created_at,
        created_by=plan.created_by
    )


@router.post("/plans/{plan_id}/approve", status_code=status.HTTP_200_OK)
async def approve_remediation_plan(
    plan_id: str,
    user: User = Depends(require_admin)
):
    """Approve a remediation plan"""
    engine = get_remediation_engine()

    success = await engine.approve_plan(plan_id, user.username)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan {plan_id} not found"
        )

    return {"status": "approved", "plan_id": plan_id, "approved_by": user.username}


@router.post("/plans/{plan_id}/execute", response_model=RemediationResultResponse)
async def execute_remediation_plan(
    plan_id: str,
    user: User = Depends(require_admin)
):
    """Execute an approved remediation plan"""
    engine = get_remediation_engine()

    try:
        result = await engine.execute_plan(plan_id)

        return RemediationResultResponse(
            plan_id=result.plan_id,
            status=result.status,
            executed_actions=result.executed_actions,
            failed_actions=result.failed_actions,
            rollback_performed=result.rollback_performed,
            start_time=result.start_time,
            end_time=result.end_time,
            duration_seconds=result.duration.total_seconds(),
            error_message=result.error_message,
            logs=result.logs
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/plans/{plan_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_remediation_plan(
    plan_id: str,
    user: User = Depends(require_admin)
):
    """Cancel a pending remediation plan"""
    engine = get_remediation_engine()

    if plan_id not in engine.pending_plans:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation plan {plan_id} not found or already executing"
        )

    plan = engine.pending_plans[plan_id]
    plan.status = RemediationStatus.CANCELLED
    del engine.pending_plans[plan_id]

    # Audit log
    audit_logger = get_audit_logger()
    if audit_logger:
        await audit_logger.log_event(
            event_type=AuditEventType.REMEDIATION_FAILED,  # Reuse FAILED for cancelled
            action="cancel_remediation_plan",
            resource_id=plan_id,
            result="cancelled",
            details={'cancelled_by': user.username}
        )

    return {"status": "cancelled", "plan_id": plan_id}


@router.get("/results/{plan_id}", response_model=RemediationResultResponse)
async def get_remediation_result(
    plan_id: str,
    user: User = Depends(require_run_rca)
):
    """Get remediation execution result"""
    engine = get_remediation_engine()
    tenant_id = get_tenant_context() or "default"

    result = engine.get_result(plan_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Remediation result {plan_id} not found"
        )

    # Check tenant access
    if result.metadata.get('tenant_id') != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this remediation result"
        )

    return RemediationResultResponse(
        plan_id=result.plan_id,
        status=result.status,
        executed_actions=result.executed_actions,
        failed_actions=result.failed_actions,
        rollback_performed=result.rollback_performed,
        start_time=result.start_time,
        end_time=result.end_time,
        duration_seconds=result.duration.total_seconds(),
        error_message=result.error_message,
        logs=result.logs
    )
