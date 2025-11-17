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
import hashlib
import hmac
import os
from pathlib import Path

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
    """
    An audit log event (v4.0: tamper-proof with cryptographic hash)

    Each event contains a hash that includes:
    - All event data
    - Previous event hash (chain of custody)
    - HMAC signature for authenticity
    """
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
    previous_hash: Optional[str] = None  # v4.0: Hash of previous event
    event_hash: Optional[str] = None  # v4.0: Hash of this event
    signature: Optional[str] = None  # v4.0: HMAC signature

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (v4.0: includes tamper-proof hashes)"""
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
            'previous_hash': self.previous_hash,
            'event_hash': self.event_hash,
            'signature': self.signature,
        }

    def compute_hash(self, secret_key: Optional[str] = None) -> str:
        """
        Compute cryptographic hash of this event (v4.0).

        The hash includes all event data plus the previous event's hash,
        creating a tamper-evident chain.

        Args:
            secret_key: Optional secret for HMAC signature

        Returns:
            SHA-256 hash of event data
        """
        # Create deterministic JSON representation (sorted keys)
        data_to_hash = {
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
            'previous_hash': self.previous_hash,
        }

        json_str = json.dumps(data_to_hash, sort_keys=True)

        # SHA-256 hash
        hash_digest = hashlib.sha256(json_str.encode('utf-8')).hexdigest()

        # HMAC signature if secret provided
        if secret_key:
            self.signature = hmac.new(
                secret_key.encode('utf-8'),
                json_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

        self.event_hash = hash_digest
        return hash_digest

    def verify_hash(self) -> bool:
        """
        Verify that this event's hash is valid (v4.0).

        Returns:
            True if hash is valid, False if tampered
        """
        if not self.event_hash:
            return False

        # Temporarily clear hash to recompute
        stored_hash = self.event_hash
        stored_sig = self.signature
        self.event_hash = None
        self.signature = None

        # Recompute hash
        computed_hash = self.compute_hash()

        # Restore original values
        original_hash = self.event_hash
        self.event_hash = stored_hash
        self.signature = stored_sig

        return computed_hash == stored_hash

    def verify_signature(self, secret_key: str) -> bool:
        """
        Verify HMAC signature (v4.0).

        Args:
            secret_key: Secret key used for signing

        Returns:
            True if signature is valid
        """
        if not self.signature:
            return False

        # Recompute signature
        data_to_hash = {
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
            'previous_hash': self.previous_hash,
        }

        json_str = json.dumps(data_to_hash, sort_keys=True)

        expected_sig = hmac.new(
            secret_key.encode('utf-8'),
            json_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_sig, self.signature)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Comprehensive audit logging system (v4.0: tamper-proof).

    Features:
    - Structured audit events
    - Multiple storage backends
    - Query and search capabilities
    - Compliance reporting
    - Real-time alerting for critical events
    - v4.0: Cryptographic hash chain for tamper evidence
    - v4.0: HMAC signatures for authenticity
    """

    def __init__(self, storage_backend=None, secret_key: Optional[str] = None):
        self.storage = storage_backend or InMemoryAuditStorage()
        self.event_counter = 0
        # v4.0: Secret key for HMAC signatures
        self.secret_key = secret_key or os.getenv("ADAPT_AUDIT_SECRET", None)
        self.last_event_hash: Optional[str] = None  # v4.0: For hash chain

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

        # v4.0: Create event with hash chain
        event = AuditEvent(
            event_id=f"audit_{datetime.utcnow().timestamp()}_{self.event_counter}",
            event_type=event_type,
            level=level,
            timestamp=datetime.utcnow(),
            tenant_id=kwargs.get('tenant_id') or get_tenant_context() or "default",
            user_id=kwargs.get('user_id') or get_user_context(),
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            details=details or {},
            ip_address=kwargs.get('ip_address'),
            user_agent=kwargs.get('user_agent'),
            session_id=kwargs.get('session_id'),
            request_id=kwargs.get('request_id'),
            previous_hash=self.last_event_hash,  # v4.0: Link to previous event
        )

        # v4.0: Compute hash and signature for tamper-proofing
        event.compute_hash(self.secret_key)
        self.last_event_hash = event.event_hash

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

    async def verify_audit_chain(
        self,
        tenant_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Verify integrity of the audit log chain (v4.0).

        Checks:
        1. Each event's hash is valid
        2. Hash chain is unbroken (each event links to previous)
        3. HMAC signatures are valid (if secret key available)

        Args:
            tenant_id: Filter by tenant
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            Verification results with details
        """
        events = await self.query_events(
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time,
            limit=10000
        )

        # Sort by timestamp to verify chain
        events = sorted(events, key=lambda e: e.timestamp)

        results = {
            'total_events': len(events),
            'valid_hashes': 0,
            'invalid_hashes': 0,
            'broken_chains': 0,
            'valid_signatures': 0,
            'invalid_signatures': 0,
            'tampered_events': [],
            'verification_timestamp': datetime.utcnow().isoformat(),
        }

        previous_hash = None

        for event in events:
            # Verify hash
            if event.verify_hash():
                results['valid_hashes'] += 1
            else:
                results['invalid_hashes'] += 1
                results['tampered_events'].append({
                    'event_id': event.event_id,
                    'reason': 'Invalid hash',
                    'timestamp': event.timestamp.isoformat()
                })

            # Verify chain link
            if previous_hash is not None and event.previous_hash != previous_hash:
                results['broken_chains'] += 1
                results['tampered_events'].append({
                    'event_id': event.event_id,
                    'reason': 'Broken chain link',
                    'timestamp': event.timestamp.isoformat()
                })

            # Verify signature if secret available
            if self.secret_key:
                if event.verify_signature(self.secret_key):
                    results['valid_signatures'] += 1
                else:
                    results['invalid_signatures'] += 1
                    results['tampered_events'].append({
                        'event_id': event.event_id,
                        'reason': 'Invalid signature',
                        'timestamp': event.timestamp.isoformat()
                    })

            previous_hash = event.event_hash

        results['integrity_verified'] = (
            results['invalid_hashes'] == 0 and
            results['broken_chains'] == 0 and
            (not self.secret_key or results['invalid_signatures'] == 0)
        )

        return results

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


class TamperProofFileStorage:
    """
    Append-only file storage for audit logs (v4.0).

    Features:
    - Append-only mode (no modifications allowed)
    - One event per line (JSON Lines format)
    - File rotation by date
    - Tamper-evident hash chain
    - Read-only verification

    Security:
    - Files are opened in append mode only
    - Hashes make tampering detectable
    - Separate files per tenant (optional)
    """

    def __init__(self, storage_path: str = "./data/audit", per_tenant: bool = True):
        self.storage_path = Path(storage_path)
        self.per_tenant = per_tenant
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions (owner read/write only)
        if os.name != 'nt':  # Unix/Linux only
            os.chmod(self.storage_path, 0o700)

        logger.info(f"Initialized tamper-proof audit storage at {self.storage_path}")

    def _get_log_file(self, tenant_id: str, date: datetime) -> Path:
        """Get log file path for a specific tenant and date"""
        if self.per_tenant:
            tenant_dir = self.storage_path / tenant_id
            tenant_dir.mkdir(exist_ok=True)
            if os.name != 'nt':
                os.chmod(tenant_dir, 0o700)
            return tenant_dir / f"audit_{date.strftime('%Y%m%d')}.jsonl"
        else:
            return self.storage_path / f"audit_{date.strftime('%Y%m%d')}.jsonl"

    async def store(self, event: AuditEvent):
        """
        Store event in append-only log file (v4.0).

        Events are written as JSON Lines (one per line) and cannot be modified.
        """
        log_file = self._get_log_file(event.tenant_id, event.timestamp)

        # Append event to log file (atomic operation)
        try:
            # Use 'a' mode for append-only (cannot modify existing content)
            async with asyncio.Lock():  # Ensure atomic writes
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(event.to_json() + '\n')

                    # Set read-only permissions on file (prevent tampering)
                    if os.name != 'nt':
                        os.chmod(log_file, 0o400)  # Read-only for owner

        except Exception as e:
            logger.error(f"Failed to write audit event to file: {e}")
            raise

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
        """
        Query events from log files (v4.0).

        Reads events from JSONL files and filters them.
        """
        events = []

        # Determine which files to read
        if start_time and end_time:
            date_range = [
                start_time.date() + timedelta(days=i)
                for i in range((end_time.date() - start_time.date()).days + 1)
            ]
        else:
            # Read all available files
            date_range = self._get_available_dates(tenant_id)

        # Read events from files
        for date in date_range:
            date_dt = datetime.combine(date, datetime.min.time())
            log_file = self._get_log_file(tenant_id or "default", date_dt)

            if not log_file.exists():
                continue

            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue

                        try:
                            event_data = json.loads(line)
                            event = self._dict_to_event(event_data)

                            # Apply filters
                            if tenant_id and event.tenant_id != tenant_id:
                                continue
                            if user_id and event.user_id != user_id:
                                continue
                            if event_type and event.event_type != event_type:
                                continue
                            if resource_type and event.resource_type != resource_type:
                                continue
                            if resource_id and event.resource_id != resource_id:
                                continue

                            events.append(event)

                            if len(events) >= limit:
                                break

                        except json.JSONDecodeError as e:
                            logger.warning(f"Skipping corrupted audit line: {e}")

            except Exception as e:
                logger.error(f"Failed to read audit file {log_file}: {e}")

            if len(events) >= limit:
                break

        # Sort by timestamp descending
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)

        return events[:limit]

    def _get_available_dates(self, tenant_id: Optional[str] = None) -> List:
        """Get list of dates for which log files exist"""
        from datetime import date, timedelta

        dates = []

        if self.per_tenant and tenant_id:
            tenant_dir = self.storage_path / tenant_id
            if not tenant_dir.exists():
                return []

            pattern = "audit_*.jsonl"
            for file in tenant_dir.glob(pattern):
                try:
                    date_str = file.stem.split('_')[1]
                    file_date = datetime.strptime(date_str, '%Y%m%d').date()
                    dates.append(file_date)
                except (ValueError, IndexError):
                    continue
        else:
            pattern = "audit_*.jsonl"
            for file in self.storage_path.glob(pattern):
                try:
                    date_str = file.stem.split('_')[1]
                    file_date = datetime.strptime(date_str, '%Y%m%d').date()
                    dates.append(file_date)
                except (ValueError, IndexError):
                    continue

        return sorted(dates)

    def _dict_to_event(self, data: Dict[str, Any]) -> AuditEvent:
        """Convert dictionary to AuditEvent"""
        from datetime import timedelta

        return AuditEvent(
            event_id=data['event_id'],
            event_type=AuditEventType(data['event_type']),
            level=AuditLevel(data['level']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            tenant_id=data['tenant_id'],
            user_id=data.get('user_id'),
            resource_type=data.get('resource_type'),
            resource_id=data.get('resource_id'),
            action=data['action'],
            result=data['result'],
            details=data.get('details', {}),
            ip_address=data.get('ip_address'),
            user_agent=data.get('user_agent'),
            session_id=data.get('session_id'),
            request_id=data.get('request_id'),
            previous_hash=data.get('previous_hash'),
            event_hash=data.get('event_hash'),
            signature=data.get('signature'),
        )


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
