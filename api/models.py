"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SignalTypeEnum(str, Enum):
    """Signal types"""
    LOG = "log"
    METRIC = "metric"
    TRACE = "trace"
    CONFIG_CHANGE = "config_change"
    ALERT = "alert"
    EVENT = "event"


class SignalRequest(BaseModel):
    """Request model for a single signal"""
    signal_type: SignalTypeEnum
    title: str
    description: str
    timestamp: datetime
    source: str
    severity: str = "medium"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: Dict[str, str] = Field(default_factory=dict)


class IncidentRequest(BaseModel):
    """Request model for creating an RCA incident"""
    incident_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    signals: List[SignalRequest]
    playbook_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RCAStartRequest(BaseModel):
    """Request to start RCA analysis"""
    incident_id: str
    signals: List[SignalRequest]
    playbook_name: Optional[str] = None
    execution_mode: str = "adaptive"


class NodeResponse(BaseModel):
    """Response model for RCA graph node"""
    id: str
    type: str
    title: str
    description: str
    confidence: float
    metadata: Dict[str, Any]
    created_at: datetime


class EdgeResponse(BaseModel):
    """Response model for RCA graph edge"""
    source: str
    target: str
    type: str
    weight: float
    metadata: Dict[str, Any]


class RCAGraphResponse(BaseModel):
    """Response model for complete RCA graph"""
    incident_id: str
    nodes: List[NodeResponse]
    edges: List[EdgeResponse]
    created_at: datetime
    metadata: Dict[str, Any]


class FindingResponse(BaseModel):
    """Response model for agent finding"""
    id: str
    title: str
    description: str
    confidence: float
    agent: str
    metadata: Dict[str, Any]


class RootCauseResponse(BaseModel):
    """Response model for identified root cause"""
    id: str
    title: str
    description: str
    confidence: float
    metadata: Dict[str, Any]


class RemediationActionResponse(BaseModel):
    """Response model for remediation action"""
    action_type: str
    description: str
    risk_level: str
    estimated_duration: Optional[str] = None
    requires_approval: bool


class RemediationPlanResponse(BaseModel):
    """Response model for remediation plan"""
    incident_id: str
    actions: List[RemediationActionResponse]
    estimated_total_duration: Optional[str] = None
    risk_assessment: str


class RCAResponse(BaseModel):
    """Complete RCA response"""
    incident_id: str
    status: str  # completed, in_progress, failed
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_time_seconds: Optional[float] = None
    root_causes: List[RootCauseResponse]
    findings: List[FindingResponse]
    graph: RCAGraphResponse
    remediation_plan: Optional[RemediationPlanResponse] = None
    narrative: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RCAListItem(BaseModel):
    """List item for RCA history"""
    incident_id: str
    status: str
    created_at: datetime
    root_causes_count: int
    findings_count: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str  # healthy, degraded, unhealthy
    timestamp: datetime
    components: List[Dict[str, Any]]


class MetricsResponse(BaseModel):
    """Metrics response"""
    rca_total: int
    rca_avg_duration_seconds: float
    agent_stats: Dict[str, Any]
    findings_stats: Dict[str, Any]


class AgentInfo(BaseModel):
    """Information about an agent"""
    name: str
    description: str
    purpose: str
    enabled: bool = True


class PlaybookSummary(BaseModel):
    """Summary of a playbook"""
    name: str
    description: str
    category: str
    version: str
    triggers: List[str]


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class UserInfo(BaseModel):
    """User information"""
    username: str
    email: Optional[str] = None
    roles: List[str]
    tenant_id: str


class TokenResponse(BaseModel):
    """Authentication token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class WebSocketUpdate(BaseModel):
    """WebSocket update message"""
    type: str  # STARTED, AGENT_STARTED, FINDING, ROOT_CAUSE, COMPLETED, ERROR
    timestamp: datetime
    data: Dict[str, Any]
