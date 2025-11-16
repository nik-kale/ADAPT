"""
Comprehensive Audit Logging System

Tracks all user actions and system events for compliance and security.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import logging
import json
import asyncio

from core.tenant import get_tenant_context, get_user_context

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events"""
    # Authentication
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    LOGIN_FAILED = "auth.login_failed"
    TOKEN_GENERATED = "auth.token_generated"
    TOKEN_REVOKED = "auth.token_revoked"

    # RCA Operations
    RCA_STARTED = "rca.started"
    RCA_COMPLETED = "rca.completed"
    RCA_FAILED = "rca.failed"
    RCA_CANCELLED = "rca.cancelled"

    # Data Access
    INCIDENT_VIEWED = "data.incident_viewed"
    INCIDENT_DELETED = "data.incident_deleted"
    GRAPH_EXPORTED = "data.graph_exported"

    # Configuration
    CONFIG_CHANGED = "config.changed"
    AGENT_ENABLED = "config.agent_enabled"
    AGENT_DISABLED = "config.agent_disabled"
    PLAYBOOK_CREATED = "config.playbook_created"
    PLAYBOOK_UPDATED = "config.playbook_updated"
    PLAYBOOK_DELETED = "config.playbook_deleted"

    # User Management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    ROLE_ASSIGNED = "user.role_assigned"
    ROLE_REVOKED = "user.role_revoked"

    # Tenant Management
    TENANT_CREATED = "tenant.created"
    TENANT_UPDATED = "tenant.updated"
    TENANT_DISABLED = "tenant.disabled"

    # Remediation
    REMEDIATION_PLAN_CREATED = "remediation.plan_created"
    REMEDIATION_APPROVED = "remediation.approved"
    REMEDIATION_EXECUTED = "remediation.executed"
    REMEDIATION_FAILED = "remediation.failed"
    REMEDIATION_ROLLED_BACK = "remediation.rolled_back"

    # Integration
    INTEGRATION_CALLED = "integration.called"
    WEBHOOK_SENT = "integration.webhook_sent"

    # Security
    PERMISSION_DENIED = "security.permission_denied"
    QUOTA_EXCEEDED = "security.quota_exceeded"
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"


class AuditLevel(str, Enum):
    """Audit event severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """An audit log event"""
    event_id: str
    event_type: AuditEventType
    level: AuditLevel
    timestamp: datetime
    tenant_id: str
    user_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    action: str
    result: str  # success, failure, denied
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'level': self.level.value,
            'timestamp': self.timestamp.isoformat(),
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'action': self.action,
            'result': self.result,
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'session_id': self.session_id,
            'request_id': self.request_id,
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Comprehensive audit logging system.

    Features:
    - Structured audit events
    - Multiple storage backends
    - Query and search capabilities
    - Compliance reporting
    - Real-time alerting for critical events
    """

    def __init__(self, storage_backend=None):
        self.storage = storage_backend or InMemoryAuditStorage()
        self.event_counter = 0

    async def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        result: str = "success",
        level: AuditLevel = AuditLevel.INFO,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            action: Action performed
            result: Result of action (success/failure/denied)
            level: Severity level
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            details: Additional event details
            **kwargs: Additional fields (ip_address, user_agent, etc.)

        Returns:
            Created audit event
        """
        self.event_counter += 1

        event = AuditEvent(
            event_id=f"audit_{datetime.utcnow().timestamp()}_{self.event_counter}",
            event_type=event_type,
            level=level,
            timestamp=datetime.utcnow(),
            tenant_id=get_tenant_context() or "default",
            user_id=get_user_context(),
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            details=details or {},
            ip_address=kwargs.get('ip_address'),
            user_agent=kwargs.get('user_agent'),
            session_id=kwargs.get('session_id'),
            request_id=kwargs.get('request_id'),
        )

        # Store event
        await self.storage.store(event)

        # Log to standard logger
        log_level = {
            AuditLevel.INFO: logging.INFO,
            AuditLevel.WARNING: logging.WARNING,
            AuditLevel.ERROR: logging.ERROR,
            AuditLevel.CRITICAL: logging.CRITICAL,
        }.get(level, logging.INFO)

        logger.log(
            log_level,
            f"AUDIT: {event_type.value} - {action} - {result}",
            extra={'audit_event': event.to_dict()}
        )

        # Alert on critical events
        if level == AuditLevel.CRITICAL:
            await self._alert_critical_event(event)

        return event

    async def query_events(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Query audit events.

        Args:
            tenant_id: Filter by tenant
            user_id: Filter by user
            event_type: Filter by event type
            start_time: Filter by start time
            end_time: Filter by end time
            resource_type: Filter by resource type
            resource_id: Filter by specific resource
            limit: Maximum number of results

        Returns:
            List of matching audit events
        """
        return await self.storage.query(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit
        )

    async def get_user_activity(
        self,
        user_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[AuditEvent]:
        """Get all activity for a user"""
        return await self.query_events(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            limit=1000
        )

    async def get_resource_history(
        self,
        resource_type: str,
        resource_id: str
    ) -> List[AuditEvent]:
        """Get all events for a specific resource"""
        return await self.query_events(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=1000
        )

    async def get_security_events(
        self,
        tenant_id: Optional[str] = None,
        start_time: Optional[datetime] = None
    ) -> List[AuditEvent]:
        """Get security-related events"""
        events = []

        security_types = [
            AuditEventType.LOGIN_FAILED,
            AuditEventType.PERMISSION_DENIED,
            AuditEventType.QUOTA_EXCEEDED,
            AuditEventType.SUSPICIOUS_ACTIVITY,
        ]

        for event_type in security_types:
            events.extend(await self.query_events(
                tenant_id=tenant_id,
                event_type=event_type,
                start_time=start_time,
                limit=100
            ))

        return sorted(events, key=lambda e: e.timestamp, reverse=True)

    async def _alert_critical_event(self, event: AuditEvent):
        """Alert on critical audit events"""
        # This could integrate with PagerDuty, Slack, etc.
        logger.critical(
            f"CRITICAL AUDIT EVENT: {event.event_type.value} - "
            f"User: {event.user_id}, Tenant: {event.tenant_id}"
        )

        # TODO: Send to alerting system


class InMemoryAuditStorage:
    """In-memory audit storage for development/testing"""

    def __init__(self):
        self.events: List[AuditEvent] = []

    async def store(self, event: AuditEvent):
        """Store event in memory"""
        self.events.append(event)

    async def query(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Query events from memory"""
        filtered = self.events

        if tenant_id:
            filtered = [e for e in filtered if e.tenant_id == tenant_id]
        if user_id:
            filtered = [e for e in filtered if e.user_id == user_id]
        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]
        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]
        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]
        if resource_type:
            filtered = [e for e in filtered if e.resource_type == resource_type]
        if resource_id:
            filtered = [e for e in filtered if e.resource_id == resource_id]

        # Sort by timestamp descending
        filtered = sorted(filtered, key=lambda e: e.timestamp, reverse=True)

        return filtered[:limit]


class PostgresAuditStorage:
    """PostgreSQL audit storage for production"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        # TODO: Initialize PostgreSQL connection

    async def store(self, event: AuditEvent):
        """Store event in PostgreSQL"""
        # TODO: Implement PostgreSQL storage
        pass

    async def query(self, **kwargs) -> List[AuditEvent]:
        """Query events from PostgreSQL"""
        # TODO: Implement PostgreSQL query
        pass


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def set_audit_logger(logger: AuditLogger):
    """Set global audit logger"""
    global _audit_logger
    _audit_logger = logger


# Convenience decorator for audit logging
def audit_action(event_type: AuditEventType, resource_type: Optional[str] = None):
    """Decorator to automatically audit function calls"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            audit_logger = get_audit_logger()

            try:
                result = await func(*args, **kwargs)

                await audit_logger.log_event(
                    event_type=event_type,
                    action=func.__name__,
                    result="success",
                    resource_type=resource_type,
                    details={'args': str(args)[:100], 'kwargs': str(kwargs)[:100]}
                )

                return result

            except Exception as e:
                await audit_logger.log_event(
                    event_type=event_type,
                    action=func.__name__,
                    result="failure",
                    level=AuditLevel.ERROR,
                    resource_type=resource_type,
                    details={'error': str(e)}
                )
                raise

        return wrapper
    return decorator
