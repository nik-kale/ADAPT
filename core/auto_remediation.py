"""
Auto-Remediation Engine

Closed-loop automation for executing remediation actions with safety controls.
Includes approval workflows, rollback capabilities, and comprehensive auditing.

v4.0: Enhanced with command injection prevention and security validation
"""

from typing import List, Dict, Any, Optional, Callable, Awaitable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import asyncio
import shlex
import re

logger = logging.getLogger(__name__)


class RemediationStatus(str, Enum):
    """Status of remediation execution"""
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class ActionRisk(str, Enum):
    """Risk level of remediation action"""
    LOW = "low"           # Read-only, safe operations
    MEDIUM = "medium"     # Service restarts, scaling
    HIGH = "high"         # Configuration changes
    CRITICAL = "critical" # Data operations, destructive actions


@dataclass
class RemediationAction:
    """
    Single remediation action (v4.0 enhanced security)

    Commands are validated to prevent injection attacks.
    """

    action_id: str
    action_type: str
    description: str
    risk_level: ActionRisk
    target_service: str
    command: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 300  # seconds
    rollback_command: Optional[str] = None
    requires_approval: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate command for security (v4.0)"""
        self._validate_command(self.command, "command")

        if self.rollback_command:
            self._validate_command(self.rollback_command, "rollback_command")

        # Validate timeout range
        if self.timeout < 1 or self.timeout > 3600:
            raise ValueError(f"timeout must be between 1 and 3600 seconds")

    def _validate_command(self, cmd: str, field_name: str):
        """
        Validate command to prevent injection attacks (v4.0 security)

        Raises:
            ValueError: If command contains dangerous patterns
        """
        if not cmd or not cmd.strip():
            raise ValueError(f"{field_name} cannot be empty")

        # Dangerous patterns that indicate command injection attempts
        dangerous_patterns = [
            (r";\s*", "command chaining with semicolon"),
            (r"\|\s*", "command piping"),
            (r">\s*", "output redirection"),
            (r"<\s*", "input redirection"),
            (r"&\s*", "background execution"),
            (r"`", "command substitution with backticks"),
            (r"\$\(", "command substitution"),
            (r"\$\{", "variable substitution"),
            (r"rm\s+-rf\s+/", "dangerous rm command"),
            (r"dd\s+if=", "dangerous dd command"),
            (r":.*\(\)\s*{.*:\|:", "fork bomb pattern"),
            (r"\beval\b", "eval command"),
            (r"\bexec\b", "exec command"),
        ]

        for pattern, description in dangerous_patterns:
            if re.search(pattern, cmd, re.IGNORECASE):
                logger.error(
                    f"Dangerous command pattern detected in {field_name}: {description}"
                )
                raise ValueError(
                    f"{field_name} contains dangerous pattern: {description}. "
                    f"Command rejected for security."
                )

        # Ensure command can be safely parsed
        try:
            shlex.split(cmd)
        except ValueError as e:
            raise ValueError(f"{field_name} has invalid syntax: {e}")

        # Additional validation: command must start with a safe program
        tokens = cmd.strip().split()
        if not tokens:
            raise ValueError(f"{field_name} cannot be empty")

        # Whitelist of allowed commands (customize based on your environment)
        allowed_commands = {
            # Service management
            "systemctl",
            "service",
            "kubectl",
            "docker",
            # AWS
            "aws",
            # Kubernetes
            "kubectl",
            "helm",
            # Monitoring
            "curl",
            "wget",
            # Custom scripts (must be in allowed paths)
            "/usr/local/bin/remediation-script",
            "/opt/adapt/scripts/remediate",
        }

        base_command = tokens[0].split("/")[-1]  # Get command without path

        # Check if command is in whitelist OR is a full path to allowed locations
        is_whitelisted = base_command in allowed_commands
        is_allowed_path = tokens[0].startswith(
            ("/usr/local/bin/", "/opt/adapt/scripts/")
        )

        if not (is_whitelisted or is_allowed_path):
            logger.warning(
                f"Command '{tokens[0]}' not in whitelist. "
                f"Consider adding to allowed_commands if safe."
            )
            # Don't fail here - just warn. Adjust based on your security requirements.
            # Uncomment next line to enforce strict whitelist:
            # raise ValueError(f"Command '{tokens[0]}' not allowed")


@dataclass
class RemediationPlan:
    """Complete remediation plan"""
    plan_id: str
    incident_id: str
    actions: List[RemediationAction]
    created_at: datetime
    created_by: str
    tenant_id: str
    status: RemediationStatus = RemediationStatus.PENDING_APPROVAL
    approval_required: bool = True
    max_risk_level: ActionRisk = ActionRisk.MEDIUM
    estimated_duration: timedelta = field(default_factory=lambda: timedelta(minutes=10))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RemediationResult:
    """Result of remediation execution"""
    plan_id: str
    status: RemediationStatus
    executed_actions: List[str]
    failed_actions: List[str]
    rollback_performed: bool
    start_time: datetime
    end_time: datetime
    duration: timedelta
    logs: List[str]
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SafetyCheck:
    """Safety checks before executing remediation"""

    @staticmethod
    async def check_action_safety(
        action: RemediationAction,
        context: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Check if action is safe to execute.

        Returns:
            (is_safe, reason)
        """
        # Check 1: Risk level within allowed threshold
        max_allowed_risk = context.get('max_risk_level', ActionRisk.MEDIUM)
        if SafetyCheck._risk_to_int(action.risk_level) > SafetyCheck._risk_to_int(max_allowed_risk):
            return False, f"Risk level {action.risk_level} exceeds maximum allowed {max_allowed_risk}"

        # Check 2: Service is not in maintenance
        if context.get('services_in_maintenance', {}).get(action.target_service):
            return False, f"Service {action.target_service} is in maintenance mode"

        # Check 3: No recent failed attempts
        recent_failures = context.get('recent_failures', {}).get(action.action_type, 0)
        if recent_failures > 3:
            return False, f"Too many recent failures for {action.action_type} ({recent_failures})"

        # Check 4: Not in freeze window
        if context.get('change_freeze', False):
            return False, "System is in change freeze window"

        # Check 5: Required dependencies available
        if action.metadata.get('requires_dependencies'):
            for dep in action.metadata['requires_dependencies']:
                if not context.get('dependencies', {}).get(dep):
                    return False, f"Required dependency {dep} not available"

        return True, "Safety checks passed"

    @staticmethod
    def _risk_to_int(risk: ActionRisk) -> int:
        """Convert risk level to integer for comparison"""
        risk_map = {
            ActionRisk.LOW: 1,
            ActionRisk.MEDIUM: 2,
            ActionRisk.HIGH: 3,
            ActionRisk.CRITICAL: 4
        }
        return risk_map.get(risk, 0)


class AutoRemediationEngine:
    """
    Auto-remediation engine with safety controls.

    Features:
    - Approval workflows
    - Safety checks
    - Rollback capability
    - Audit logging
    - Progress tracking
    """

    def __init__(
        self,
        auto_approve_low_risk: bool = True,
        max_concurrent_actions: int = 3,
        default_timeout: int = 300
    ):
        self.auto_approve_low_risk = auto_approve_low_risk
        self.max_concurrent_actions = max_concurrent_actions
        self.default_timeout = default_timeout
        self.pending_plans: Dict[str, RemediationPlan] = {}
        self.executing_plans: Dict[str, RemediationPlan] = {}
        self.completed_plans: Dict[str, RemediationResult] = {}
        self.action_executors: Dict[str, Callable] = {}
        self._register_default_executors()

    def _register_default_executors(self):
        """Register default action executors"""
        self.action_executors.update({
            'restart_service': self._execute_restart_service,
            'scale_service': self._execute_scale_service,
            'update_config': self._execute_update_config,
            'clear_cache': self._execute_clear_cache,
            'rollback_deployment': self._execute_rollback_deployment,
            'kill_process': self._execute_kill_process,
            'drain_traffic': self._execute_drain_traffic,
        })

    def register_executor(
        self,
        action_type: str,
        executor: Callable[[RemediationAction, Dict], Awaitable[Tuple[bool, str]]]
    ):
        """
        Register custom action executor.

        Args:
            action_type: Type of action
            executor: Async function that executes the action
        """
        self.action_executors[action_type] = executor
        logger.info(f"Registered executor for action type: {action_type}")

    async def submit_plan(self, plan: RemediationPlan) -> str:
        """
        Submit remediation plan for approval/execution.

        Args:
            plan: Remediation plan to submit

        Returns:
            Plan ID
        """
        from core.audit import get_audit_logger, AuditEventType

        # Auto-approve low-risk plans if configured
        if self.auto_approve_low_risk and plan.max_risk_level == ActionRisk.LOW:
            plan.status = RemediationStatus.APPROVED
            plan.approval_required = False
            logger.info(f"Auto-approved low-risk plan: {plan.plan_id}")

            # Log approval
            audit_logger = get_audit_logger()
            if audit_logger:
                await audit_logger.log_event(
                    event_type=AuditEventType.REMEDIATION_APPROVED,
                    action="auto_approve_remediation",
                    resource_id=plan.plan_id,
                    result="success",
                    details={'reason': 'low_risk_auto_approval'}
                )

        self.pending_plans[plan.plan_id] = plan
        logger.info(
            f"Submitted remediation plan {plan.plan_id} with {len(plan.actions)} actions "
            f"(status: {plan.status})"
        )

        return plan.plan_id

    async def approve_plan(self, plan_id: str, approver: str) -> bool:
        """
        Approve a pending remediation plan.

        Args:
            plan_id: Plan identifier
            approver: User approving the plan

        Returns:
            True if approved successfully
        """
        from core.audit import get_audit_logger, AuditEventType

        if plan_id not in self.pending_plans:
            logger.error(f"Plan {plan_id} not found in pending plans")
            return False

        plan = self.pending_plans[plan_id]
        plan.status = RemediationStatus.APPROVED
        plan.metadata['approved_by'] = approver
        plan.metadata['approved_at'] = datetime.utcnow().isoformat()

        logger.info(f"Plan {plan_id} approved by {approver}")

        # Log approval
        audit_logger = get_audit_logger()
        if audit_logger:
            await audit_logger.log_event(
                event_type=AuditEventType.REMEDIATION_APPROVED,
                action="approve_remediation",
                resource_id=plan_id,
                result="success",
                details={'approver': approver}
            )

        return True

    async def execute_plan(self, plan_id: str) -> RemediationResult:
        """
        Execute approved remediation plan.

        Args:
            plan_id: Plan identifier

        Returns:
            Remediation result
        """
        from core.audit import get_audit_logger, AuditEventType

        if plan_id not in self.pending_plans:
            raise ValueError(f"Plan {plan_id} not found")

        plan = self.pending_plans[plan_id]

        if plan.status != RemediationStatus.APPROVED:
            raise ValueError(f"Plan {plan_id} is not approved (status: {plan.status})")

        # Move to executing
        plan.status = RemediationStatus.EXECUTING
        self.executing_plans[plan_id] = plan
        del self.pending_plans[plan_id]

        start_time = datetime.utcnow()
        executed_actions = []
        failed_actions = []
        logs = []
        rollback_performed = False
        error_message = None

        logger.info(f"Starting execution of plan {plan_id}")

        # Log execution start
        audit_logger = get_audit_logger()
        if audit_logger:
            await audit_logger.log_event(
                event_type=AuditEventType.REMEDIATION_EXECUTED,
                action="execute_remediation",
                resource_id=plan_id,
                result="started",
                details={'action_count': len(plan.actions)}
            )

        try:
            # Execute actions sequentially
            for action in plan.actions:
                logs.append(f"[{datetime.utcnow()}] Executing action: {action.description}")

                # Safety check
                is_safe, reason = await SafetyCheck.check_action_safety(
                    action,
                    context={
                        'max_risk_level': plan.max_risk_level,
                        'services_in_maintenance': {},
                        'recent_failures': {},
                        'change_freeze': False,
                    }
                )

                if not is_safe:
                    logs.append(f"[{datetime.utcnow()}] Safety check failed: {reason}")
                    failed_actions.append(action.action_id)
                    error_message = f"Safety check failed for {action.action_id}: {reason}"
                    break

                # Execute action
                success, message = await self._execute_action(action)

                if success:
                    logs.append(f"[{datetime.utcnow()}] Action succeeded: {message}")
                    executed_actions.append(action.action_id)
                else:
                    logs.append(f"[{datetime.utcnow()}] Action failed: {message}")
                    failed_actions.append(action.action_id)
                    error_message = message

                    # Attempt rollback
                    if action.rollback_command:
                        logs.append(f"[{datetime.utcnow()}] Attempting rollback...")
                        rollback_success = await self._rollback_action(action)
                        rollback_performed = True

                        if rollback_success:
                            logs.append(f"[{datetime.utcnow()}] Rollback successful")
                        else:
                            logs.append(f"[{datetime.utcnow()}] Rollback failed")

                    break  # Stop on first failure

            # Determine final status
            if failed_actions:
                final_status = RemediationStatus.ROLLED_BACK if rollback_performed else RemediationStatus.FAILED
            else:
                final_status = RemediationStatus.SUCCESS

            plan.status = final_status

        except Exception as e:
            logger.error(f"Exception during plan execution: {e}")
            final_status = RemediationStatus.FAILED
            error_message = str(e)
            logs.append(f"[{datetime.utcnow()}] Exception: {e}")

        end_time = datetime.utcnow()
        duration = end_time - start_time

        # Create result
        result = RemediationResult(
            plan_id=plan_id,
            status=final_status,
            executed_actions=executed_actions,
            failed_actions=failed_actions,
            rollback_performed=rollback_performed,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            logs=logs,
            error_message=error_message,
            metadata={
                'incident_id': plan.incident_id,
                'total_actions': len(plan.actions),
                'tenant_id': plan.tenant_id
            }
        )

        # Store result
        self.completed_plans[plan_id] = result
        if plan_id in self.executing_plans:
            del self.executing_plans[plan_id]

        logger.info(
            f"Completed plan {plan_id}: {final_status} "
            f"({len(executed_actions)}/{len(plan.actions)} actions succeeded)"
        )

        # Log completion
        if audit_logger:
            await audit_logger.log_event(
                event_type=AuditEventType.REMEDIATION_EXECUTED,
                action="complete_remediation",
                resource_id=plan_id,
                result="success" if final_status == RemediationStatus.SUCCESS else "failure",
                details={
                    'status': final_status,
                    'executed_actions': len(executed_actions),
                    'failed_actions': len(failed_actions)
                }
            )

        return result

    async def _execute_action(self, action: RemediationAction) -> Tuple[bool, str]:
        """Execute single remediation action"""
        try:
            # Find executor
            executor = self.action_executors.get(action.action_type)
            if not executor:
                return False, f"No executor found for action type: {action.action_type}"

            # Execute with timeout
            success, message = await asyncio.wait_for(
                executor(action, {}),
                timeout=action.timeout
            )

            return success, message

        except asyncio.TimeoutError:
            return False, f"Action timed out after {action.timeout} seconds"
        except Exception as e:
            return False, f"Action failed with exception: {e}"

    async def _rollback_action(self, action: RemediationAction) -> bool:
        """Rollback a remediation action"""
        try:
            if not action.rollback_command:
                return False

            logger.info(f"Rolling back action {action.action_id}")
            # Execute rollback command
            # In production, would actually execute the rollback
            await asyncio.sleep(1)  # Simulate rollback
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    # Default action executors (simulated)

    async def _execute_restart_service(
        self, action: RemediationAction, context: Dict
    ) -> Tuple[bool, str]:
        """Restart a service"""
        service = action.target_service
        logger.info(f"Restarting service: {service}")

        # In production, would use kubectl/systemctl/etc
        # kubectl rollout restart deployment/{service}
        await asyncio.sleep(2)  # Simulate restart

        return True, f"Service {service} restarted successfully"

    async def _execute_scale_service(
        self, action: RemediationAction, context: Dict
    ) -> Tuple[bool, str]:
        """Scale a service"""
        service = action.target_service
        replicas = action.parameters.get('replicas', 3)

        logger.info(f"Scaling service {service} to {replicas} replicas")

        # In production: kubectl scale deployment/{service} --replicas={replicas}
        await asyncio.sleep(1)

        return True, f"Service {service} scaled to {replicas} replicas"

    async def _execute_update_config(
        self, action: RemediationAction, context: Dict
    ) -> Tuple[bool, str]:
        """Update configuration"""
        service = action.target_service
        config_key = action.parameters.get('key')
        config_value = action.parameters.get('value')

        logger.info(f"Updating config {config_key}={config_value} for {service}")

        # In production: kubectl patch configmap/{service} -p '{...}'
        await asyncio.sleep(1)

        return True, f"Configuration updated for {service}"

    async def _execute_clear_cache(
        self, action: RemediationAction, context: Dict
    ) -> Tuple[bool, str]:
        """Clear cache"""
        service = action.target_service

        logger.info(f"Clearing cache for {service}")

        # In production: redis-cli FLUSHDB or similar
        await asyncio.sleep(0.5)

        return True, f"Cache cleared for {service}"

    async def _execute_rollback_deployment(
        self, action: RemediationAction, context: Dict
    ) -> Tuple[bool, str]:
        """Rollback deployment"""
        service = action.target_service

        logger.info(f"Rolling back deployment for {service}")

        # In production: kubectl rollout undo deployment/{service}
        await asyncio.sleep(2)

        return True, f"Deployment rolled back for {service}"

    async def _execute_kill_process(
        self, action: RemediationAction, context: Dict
    ) -> Tuple[bool, str]:
        """Kill a process"""
        process_id = action.parameters.get('pid')

        logger.info(f"Killing process {process_id}")

        # In production: kill -9 {process_id} or kubectl delete pod
        await asyncio.sleep(0.5)

        return True, f"Process {process_id} terminated"

    async def _execute_drain_traffic(
        self, action: RemediationAction, context: Dict
    ) -> Tuple[bool, str]:
        """Drain traffic from service"""
        service = action.target_service

        logger.info(f"Draining traffic from {service}")

        # In production: update load balancer weights
        await asyncio.sleep(1)

        return True, f"Traffic drained from {service}"

    def get_plan_status(self, plan_id: str) -> Optional[RemediationStatus]:
        """Get status of a remediation plan"""
        # Check all storage locations
        if plan_id in self.pending_plans:
            return self.pending_plans[plan_id].status
        elif plan_id in self.executing_plans:
            return self.executing_plans[plan_id].status
        elif plan_id in self.completed_plans:
            return self.completed_plans[plan_id].status
        return None

    def get_result(self, plan_id: str) -> Optional[RemediationResult]:
        """Get result of completed remediation"""
        return self.completed_plans.get(plan_id)


# Global auto-remediation engine
_remediation_engine: Optional[AutoRemediationEngine] = None


def get_remediation_engine() -> AutoRemediationEngine:
    """Get global remediation engine"""
    global _remediation_engine
    if _remediation_engine is None:
        _remediation_engine = AutoRemediationEngine()
    return _remediation_engine
