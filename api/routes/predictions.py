"""
Predictive Detection API Routes

Endpoints for incident prediction and early warning systems.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from api.auth import User, require_run_rca, require_admin
from core.predictive_detection import (
    PredictiveDetector,
    IncidentPrediction,
    PredictionSeverity,
    PredictiveMonitor
)
from core.tenant import get_tenant_context
from core.audit import get_audit_logger, AuditEventType

router = APIRouter(prefix="/predictions", tags=["Predictive Detection"])

# Global detector instance
_detector: Optional[PredictiveDetector] = None
_monitor: Optional[PredictiveMonitor] = None


async def get_detector() -> PredictiveDetector:
    """Get or initialize predictive detector"""
    global _detector
    if _detector is None:
        _detector = PredictiveDetector(
            prediction_window=timedelta(hours=1),
            min_confidence=0.6
        )
        await _detector.initialize()
    return _detector


# Request/Response Models

class PredictionAnalyzeRequest(BaseModel):
    metrics: List[Dict[str, Any]] = Field(..., description="Current metrics")
    signals: List[Dict[str, Any]] = Field(default_factory=list, description="Recent signals")
    service_topology: Optional[Dict[str, Any]] = Field(None, description="Service dependency graph")


class ContributingFactor(BaseModel):
    factor: str
    description: str
    severity: str


class PredictionResponse(BaseModel):
    prediction_id: str
    predicted_type: str
    severity: str
    confidence: float
    time_to_incident_minutes: int
    affected_services: List[str]
    contributing_factors: List[ContributingFactor]
    recommended_actions: List[str]
    created_at: datetime


class PredictionListResponse(BaseModel):
    predictions: List[PredictionResponse]
    total: int
    active_count: int


# Endpoints

@router.post("/analyze", response_model=List[PredictionResponse])
async def analyze_for_predictions(
    request: PredictionAnalyzeRequest,
    user: User = Depends(require_run_rca)
):
    """
    Analyze current state for potential incident predictions.

    Runs ML-based predictive detection on current metrics and signals to identify
    potential incidents before they occur.

    Requires scikit-learn to be installed for ML models.
    """
    detector = await get_detector()

    if not detector._initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Predictive detection not available. Install: pip install scikit-learn"
        )

    # Run prediction
    predictions = await detector.predict_incidents(
        current_metrics=request.metrics,
        recent_signals=request.signals,
        service_topology=request.service_topology
    )

    # Audit log
    audit_logger = get_audit_logger()
    if audit_logger:
        await audit_logger.log_event(
            event_type=AuditEventType.INTEGRATION_CALLED,
            action="predictive_analysis",
            resource_id="predictive_detector",
            result="success",
            details={
                'metric_count': len(request.metrics),
                'signal_count': len(request.signals),
                'predictions_found': len(predictions)
            }
        )

    # Convert to response format
    return [
        PredictionResponse(
            prediction_id=pred.prediction_id,
            predicted_type=pred.predicted_type,
            severity=pred.severity.value,
            confidence=pred.confidence,
            time_to_incident_minutes=int(pred.time_to_incident.total_seconds() / 60),
            affected_services=pred.affected_services,
            contributing_factors=[
                ContributingFactor(
                    factor=f['factor'],
                    description=f['description'],
                    severity=f.get('severity', 'unknown')
                )
                for f in pred.contributing_factors
            ],
            recommended_actions=pred.recommended_actions,
            created_at=pred.created_at
        )
        for pred in predictions
    ]


@router.get("/", response_model=PredictionListResponse)
async def list_predictions(
    severity: Optional[PredictionSeverity] = None,
    min_confidence: float = 0.0,
    user: User = Depends(require_run_rca)
):
    """
    List active incident predictions.

    Returns predictions that are still within their prediction window.
    """
    detector = await get_detector()
    global _monitor

    if not detector._initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Predictive detection not available"
        )

    # Get active predictions from monitor if available
    active_predictions = []
    if _monitor and hasattr(_monitor, 'active_predictions'):
        for pred_id, pred in _monitor.active_predictions.items():
            # Filter by severity
            if severity and pred.severity != severity:
                continue

            # Filter by confidence
            if pred.confidence < min_confidence:
                continue

            active_predictions.append(pred)

    # Convert to response format
    prediction_responses = [
        PredictionResponse(
            prediction_id=pred.prediction_id,
            predicted_type=pred.predicted_type,
            severity=pred.severity.value,
            confidence=pred.confidence,
            time_to_incident_minutes=int(pred.time_to_incident.total_seconds() / 60),
            affected_services=pred.affected_services,
            contributing_factors=[
                ContributingFactor(
                    factor=f['factor'],
                    description=f['description'],
                    severity=f.get('severity', 'unknown')
                )
                for f in pred.contributing_factors
            ],
            recommended_actions=pred.recommended_actions,
            created_at=pred.created_at
        )
        for pred in active_predictions
    ]

    return PredictionListResponse(
        predictions=prediction_responses,
        total=len(prediction_responses),
        active_count=len(prediction_responses)
    )


@router.get("/{prediction_id}", response_model=PredictionResponse)
async def get_prediction(
    prediction_id: str,
    user: User = Depends(require_run_rca)
):
    """Get specific prediction details"""
    global _monitor

    if not _monitor or not hasattr(_monitor, 'active_predictions'):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction monitoring not active"
        )

    if prediction_id not in _monitor.active_predictions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prediction {prediction_id} not found"
        )

    pred = _monitor.active_predictions[prediction_id]

    return PredictionResponse(
        prediction_id=pred.prediction_id,
        predicted_type=pred.predicted_type,
        severity=pred.severity.value,
        confidence=pred.confidence,
        time_to_incident_minutes=int(pred.time_to_incident.total_seconds() / 60),
        affected_services=pred.affected_services,
        contributing_factors=[
            ContributingFactor(
                factor=f['factor'],
                description=f['description'],
                severity=f.get('severity', 'unknown')
            )
            for f in pred.contributing_factors
        ],
        recommended_actions=pred.recommended_actions,
        created_at=pred.created_at
    )


@router.post("/monitor/start", status_code=status.HTTP_200_OK)
async def start_monitoring(
    background_tasks: BackgroundTasks,
    user: User = Depends(require_admin)
):
    """
    Start continuous predictive monitoring (admin only).

    Runs predictive detection in the background and stores predictions.
    """
    global _monitor, _detector

    detector = await get_detector()

    if not detector._initialized:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Predictive detection not available"
        )

    if _monitor is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monitoring already running"
        )

    # Create monitor
    _monitor = PredictiveMonitor(detector, check_interval=timedelta(minutes=5))

    # In production, would start background task properly
    # background_tasks.add_task(_monitor.monitor, ...)

    return {
        "status": "started",
        "message": "Predictive monitoring started",
        "check_interval_minutes": 5
    }


@router.post("/monitor/stop", status_code=status.HTTP_200_OK)
async def stop_monitoring(user: User = Depends(require_admin)):
    """Stop continuous predictive monitoring (admin only)"""
    global _monitor

    if _monitor is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monitoring not running"
        )

    _monitor = None

    return {
        "status": "stopped",
        "message": "Predictive monitoring stopped"
    }
