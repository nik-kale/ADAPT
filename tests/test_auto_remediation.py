"""
Tests for Auto-Remediation Engine
"""

import pytest
from datetime import datetime, timedelta
from core.auto_remediation import (
    AutoRemediationEngine,
    RemediationAction,
    RemediationPlan,
    RemediationStatus,
    ActionRisk,
    SafetyCheck,
)


@pytest.fixture
def remediation_engine():
    """Create auto-remediation engine for testing"""
    return AutoRemediationEngine(auto_approve_low_risk=True)


@pytest.fixture
def low_risk_action():
    """Create a low-risk remediation action"""
    return RemediationAction(
        action_id="action_001",
        action_type="clear_cache",
        description="Clear application cache",
        risk_level=ActionRisk.LOW,
        target_service="api-service",
        command="redis-cli FLUSHDB",
        rollback_command=None,
        requires_approval=False
    )


@pytest.fixture
def high_risk_action():
    """Create a high-risk remediation action"""
    return RemediationAction(
        action_id="action_002",
        action_type="update_config",
        description="Update database configuration",
        risk_level=ActionRisk.HIGH,
        target_service="postgres",
        command="kubectl patch configmap/postgres-config",
        rollback_command="kubectl patch configmap/postgres-config --type=restore",
        requires_approval=True
    )


@pytest.fixture
def remediation_plan(low_risk_action):
    """Create a remediation plan"""
    return RemediationPlan(
        plan_id="plan_001",
        incident_id="inc_001",
        actions=[low_risk_action],
        created_at=datetime.utcnow(),
        created_by="system",
        tenant_id="default",
        max_risk_level=ActionRisk.LOW
    )


class TestRemediationAction:
    """Test RemediationAction dataclass"""

    def test_action_creation(self, low_risk_action):
        """Test creating a remediation action"""
        assert low_risk_action.action_id == "action_001"
        assert low_risk_action.action_type == "clear_cache"
        assert low_risk_action.risk_level == ActionRisk.LOW
        assert low_risk_action.target_service == "api-service"

    def test_high_risk_action_with_rollback(self, high_risk_action):
        """Test high-risk action has rollback"""
        assert high_risk_action.risk_level == ActionRisk.HIGH
        assert high_risk_action.rollback_command is not None
        assert high_risk_action.requires_approval is True


class TestSafetyCheck:
    """Test safety check functionality"""

    @pytest.mark.asyncio
    async def test_safe_action_passes(self, low_risk_action):
        """Test that safe action passes safety checks"""
        is_safe, reason = await SafetyCheck.check_action_safety(
            low_risk_action,
            context={'max_risk_level': ActionRisk.MEDIUM}
        )

        assert is_safe is True
        assert "passed" in reason.lower()

    @pytest.mark.asyncio
    async def test_risk_level_exceeds_maximum(self, high_risk_action):
        """Test that high-risk action fails when max is medium"""
        is_safe, reason = await SafetyCheck.check_action_safety(
            high_risk_action,
            context={'max_risk_level': ActionRisk.MEDIUM}
        )

        assert is_safe is False
        assert "risk level" in reason.lower()

    @pytest.mark.asyncio
    async def test_service_in_maintenance(self, low_risk_action):
        """Test that action fails for service in maintenance"""
        is_safe, reason = await SafetyCheck.check_action_safety(
            low_risk_action,
            context={
                'max_risk_level': ActionRisk.HIGH,
                'services_in_maintenance': {'api-service': True}
            }
        )

        assert is_safe is False
        assert "maintenance" in reason.lower()

    @pytest.mark.asyncio
    async def test_change_freeze_window(self, low_risk_action):
        """Test that action fails during change freeze"""
        is_safe, reason = await SafetyCheck.check_action_safety(
            low_risk_action,
            context={
                'max_risk_level': ActionRisk.HIGH,
                'change_freeze': True
            }
        )

        assert is_safe is False
        assert "freeze" in reason.lower()

    @pytest.mark.asyncio
    async def test_too_many_recent_failures(self, low_risk_action):
        """Test that action fails with too many recent failures"""
        is_safe, reason = await SafetyCheck.check_action_safety(
            low_risk_action,
            context={
                'max_risk_level': ActionRisk.HIGH,
                'recent_failures': {'clear_cache': 5}
            }
        )

        assert is_safe is False
        assert "failures" in reason.lower()


@pytest.mark.asyncio
class TestAutoRemediationEngine:
    """Test auto-remediation engine"""

    async def test_submit_low_risk_plan_auto_approves(
        self, remediation_engine, remediation_plan
    ):
        """Test that low-risk plans are auto-approved"""
        plan_id = await remediation_engine.submit_plan(remediation_plan)

        assert plan_id == remediation_plan.plan_id
        assert remediation_plan.status == RemediationStatus.APPROVED
        assert remediation_plan.approval_required is False

    async def test_submit_high_risk_plan_needs_approval(
        self, remediation_engine, high_risk_action
    ):
        """Test that high-risk plans need approval"""
        plan = RemediationPlan(
            plan_id="plan_high_risk",
            incident_id="inc_002",
            actions=[high_risk_action],
            created_at=datetime.utcnow(),
            created_by="system",
            tenant_id="default",
            max_risk_level=ActionRisk.HIGH
        )

        plan_id = await remediation_engine.submit_plan(plan)

        assert plan.status == RemediationStatus.PENDING_APPROVAL
        assert plan.approval_required is True

    async def test_approve_plan(self, remediation_engine):
        """Test approving a remediation plan"""
        plan = RemediationPlan(
            plan_id="plan_to_approve",
            incident_id="inc_003",
            actions=[],
            created_at=datetime.utcnow(),
            created_by="system",
            tenant_id="default",
            status=RemediationStatus.PENDING_APPROVAL
        )

        await remediation_engine.submit_plan(plan)
        success = await remediation_engine.approve_plan("plan_to_approve", "admin")

        assert success is True
        assert plan.status == RemediationStatus.APPROVED
        assert plan.metadata.get('approved_by') == "admin"

    async def test_execute_approved_plan(self, remediation_engine, remediation_plan):
        """Test executing an approved plan"""
        # Submit and auto-approve
        await remediation_engine.submit_plan(remediation_plan)

        # Execute
        result = await remediation_engine.execute_plan(remediation_plan.plan_id)

        assert result.status == RemediationStatus.SUCCESS
        assert len(result.executed_actions) == 1
        assert len(result.failed_actions) == 0
        assert result.rollback_performed is False

    async def test_execute_unapproved_plan_fails(self, remediation_engine):
        """Test that unapproved plan cannot be executed"""
        plan = RemediationPlan(
            plan_id="plan_unapproved",
            incident_id="inc_004",
            actions=[],
            created_at=datetime.utcnow(),
            created_by="system",
            tenant_id="default",
            status=RemediationStatus.PENDING_APPROVAL,
            approval_required=True
        )

        # Don't auto-approve
        engine = AutoRemediationEngine(auto_approve_low_risk=False)
        await engine.submit_plan(plan)

        with pytest.raises(ValueError, match="not approved"):
            await engine.execute_plan(plan.plan_id)

    async def test_get_plan_status(self, remediation_engine, remediation_plan):
        """Test getting plan status"""
        await remediation_engine.submit_plan(remediation_plan)

        status = remediation_engine.get_plan_status(remediation_plan.plan_id)
        assert status == RemediationStatus.APPROVED

    async def test_get_result(self, remediation_engine, remediation_plan):
        """Test getting remediation result"""
        await remediation_engine.submit_plan(remediation_plan)
        await remediation_engine.execute_plan(remediation_plan.plan_id)

        result = remediation_engine.get_result(remediation_plan.plan_id)
        assert result is not None
        assert result.status == RemediationStatus.SUCCESS

    async def test_register_custom_executor(self, remediation_engine):
        """Test registering custom action executor"""
        async def custom_executor(action, context):
            return True, "Custom action executed"

        remediation_engine.register_executor("custom_action", custom_executor)

        assert "custom_action" in remediation_engine.action_executors

        # Test custom action
        action = RemediationAction(
            action_id="custom_001",
            action_type="custom_action",
            description="Custom action",
            risk_level=ActionRisk.LOW,
            target_service="test",
            command="custom command"
        )

        success, message = await remediation_engine._execute_action(action)
        assert success is True
        assert message == "Custom action executed"

    async def test_action_timeout(self, remediation_engine):
        """Test that actions timeout properly"""
        async def slow_executor(action, context):
            import asyncio
            await asyncio.sleep(10)  # Longer than timeout
            return True, "Should not reach here"

        remediation_engine.register_executor("slow_action", slow_executor)

        action = RemediationAction(
            action_id="slow_001",
            action_type="slow_action",
            description="Slow action",
            risk_level=ActionRisk.LOW,
            target_service="test",
            command="slow",
            timeout=1  # 1 second timeout
        )

        success, message = await remediation_engine._execute_action(action)
        assert success is False
        assert "timed out" in message.lower()


class TestRemediationPlan:
    """Test RemediationPlan"""

    def test_plan_creation(self, remediation_plan):
        """Test creating a remediation plan"""
        assert remediation_plan.plan_id == "plan_001"
        assert remediation_plan.incident_id == "inc_001"
        assert len(remediation_plan.actions) == 1
        assert remediation_plan.status == RemediationStatus.PENDING_APPROVAL

    def test_plan_with_multiple_actions(self, low_risk_action):
        """Test plan with multiple actions"""
        actions = [low_risk_action for _ in range(3)]

        plan = RemediationPlan(
            plan_id="plan_multi",
            incident_id="inc_005",
            actions=actions,
            created_at=datetime.utcnow(),
            created_by="system",
            tenant_id="default"
        )

        assert len(plan.actions) == 3


class TestRemediationResult:
    """Test RemediationResult"""

    @pytest.mark.asyncio
    async def test_result_contains_execution_details(
        self, remediation_engine, remediation_plan
    ):
        """Test that result contains execution details"""
        await remediation_engine.submit_plan(remediation_plan)
        result = await remediation_engine.execute_plan(remediation_plan.plan_id)

        assert result.plan_id == remediation_plan.plan_id
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.duration >= timedelta(0)
        assert len(result.logs) > 0
        assert result.metadata.get('incident_id') == remediation_plan.incident_id
