"""
Pydantic models for API requests and responses.

v4.0: Enhanced with comprehensive input validation
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import json
import re


class SignalTypeEnum(str, Enum):
    """Signal types"""
    LOG = "log"
    METRIC = "metric"
    TRACE = "trace"
    CONFIG_CHANGE = "config_change"
    ALERT = "alert"
    EVENT = "event"


class SignalRequest(BaseModel):
    """Request model for a single signal (v4.0 enhanced validation)"""

    signal_type: SignalTypeEnum
    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1, max_length=4096)
    timestamp: datetime
    source: str = Field(..., min_length=1, max_length=256)
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    metadata: Dict[str, Any] = Field(default_factory=dict, max_items=100)
    tags: Dict[str, str] = Field(default_factory=dict, max_items=50)

    @field_validator("metadata")
    @classmethod
    def validate_metadata_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Prevent oversized metadata (v4.0 security)"""
        serialized = json.dumps(v)
        max_size = 100 * 1024  # 100KB limit

        if len(serialized) > max_size:
            raise ValueError(
                f"metadata too large: {len(serialized)} bytes (max {max_size})"
            )

        # Prevent deeply nested objects (DoS protection)
        def check_depth(obj: Any, depth: int = 0, max_depth: int = 10) -> None:
            if depth > max_depth:
                raise ValueError(f"metadata nesting too deep (max {max_depth} levels)")

            if isinstance(obj, dict):
                for val in obj.values():
                    check_depth(val, depth + 1, max_depth)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    check_depth(item, depth + 1, max_depth)

        check_depth(v)
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate tag keys and values (v4.0 security)"""
        for key, value in v.items():
            # Tag keys must be alphanumeric with underscores/hyphens
            if not re.match(r"^[a-zA-Z0-9_-]+$", key):
                raise ValueError(f"Invalid tag key: {key}")

            # Tag keys and values have size limits
            if len(key) > 64:
                raise ValueError(f"Tag key too long: {key}")

            if len(value) > 256:
                raise ValueError(f"Tag value too long for key {key}")

        return v

    @field_validator("title", "description", "source")
    @classmethod
    def sanitize_strings(cls, v: str) -> str:
        """Sanitize string fields to prevent injection (v4.0 security)"""
        # Remove null bytes and other control characters
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", v)

        # Remove leading/trailing whitespace
        sanitized = sanitized.strip()

        if not sanitized:
            raise ValueError("Field cannot be empty after sanitization")

        return sanitized


class IncidentRequest(BaseModel):
    """Request model for creating an RCA incident (v4.0 enhanced validation)"""

    incident_id: Optional[str] = Field(None, min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = Field(None, max_length=4096)
    signals: List[SignalRequest] = Field(..., min_items=1, max_items=1000)
    playbook_name: Optional[str] = Field(None, min_length=1, max_length=128)
    metadata: Dict[str, Any] = Field(default_factory=dict, max_items=100)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate incident ID format (v4.0 security)"""
        if v is None:
            return v

        # Incident IDs must be alphanumeric with hyphens/underscores
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "incident_id must contain only alphanumeric characters, "
                "hyphens, and underscores"
            )

        return v

    @field_validator("playbook_name")
    @classmethod
    def validate_playbook_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate playbook name format (v4.0 security)"""
        if v is None:
            return v

        # Playbook names must be alphanumeric with underscores
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                "playbook_name must contain only alphanumeric characters "
                "and underscores"
            )

        return v


class RCAStartRequest(BaseModel):
    """Request to start RCA analysis (v4.0 enhanced validation)"""

    incident_id: str = Field(..., min_length=1, max_length=128)
    signals: List[SignalRequest] = Field(..., min_items=1, max_items=1000)
    playbook_name: Optional[str] = Field(None, min_length=1, max_length=128)
    execution_mode: str = Field(
        default="adaptive", pattern="^(sequential|parallel|adaptive)$"
    )

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, v: str) -> str:
        """Validate incident ID format (v4.0 security)"""
        # Incident IDs must be alphanumeric with hyphens/underscores
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "incident_id must contain only alphanumeric characters, "
                "hyphens, and underscores"
            )

        return v

    @field_validator("playbook_name")
    @classmethod
    def validate_playbook_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate playbook name format (v4.0 security)"""
        if v is None:
            return v

        # Playbook names must be alphanumeric with underscores
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                "playbook_name must contain only alphanumeric characters "
                "and underscores"
            )

        return v


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
