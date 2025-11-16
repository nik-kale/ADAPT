# ADAPT v3.0 Integration Gaps - Quick Fix Guide

## Critical Issues (Prevents Code Execution)

### 1. Fix: Missing `Tuple` Import
**File:** `/home/user/ADAPT/core/auto_remediation.py`
**Line:** 8

**Current:**
```python
from typing import List, Dict, Any, Optional, Callable, Awaitable
```

**Fix:**
```python
from typing import List, Dict, Any, Optional, Callable, Awaitable, Tuple
```

---

### 2. Fix: Missing Audit Event Types
**File:** `/home/user/ADAPT/core/audit.py`
**Line:** 67 (before closing of AuditEventType enum)

**Current:**
```python
    # Security
    PERMISSION_DENIED = "security.permission_denied"
    QUOTA_EXCEEDED = "security.quota_exceeded"
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"
```

**Fix:**
```python
    # Security
    PERMISSION_DENIED = "security.permission_denied"
    QUOTA_EXCEEDED = "security.quota_exceeded"
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"

    # Remediation
    REMEDIATION_APPROVED = "remediation.approved"
    REMEDIATION_EXECUTED = "remediation.executed"
```

---

## High Priority Issues (Missing Functionality)

### 3. Fix: Export V3 Modules from core/__init__.py
**File:** `/home/user/ADAPT/core/__init__.py`
**Location:** Lines 20-47 (imports) and Lines 49-122 (__all__)

**Add Imports After Line 47:**
```python
from .tenant import (
    TenantManager,
    TenantConfig,
    TenantAwareOrchestrator,
    TenantAwareGraphStorage,
    get_tenant_manager,
    set_tenant_context,
    get_tenant_context,
    set_user_context,
    get_user_context,
)
from .audit import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditLevel,
    get_audit_logger,
    set_audit_logger,
)
from .pii_scrubber import (
    PIIScrubber,
    get_pii_scrubber,
    set_pii_scrubber,
)
from .knowledge_base import (
    KnowledgeBase,
    KnowledgeEntry,
    RAGEnhancedOrchestrator,
)
from .auto_remediation import (
    AutoRemediationEngine,
    RemediationPlan,
    RemediationAction,
    RemediationResult,
    get_remediation_engine,
    SafetyCheck,
)
from .predictive_detection import (
    PredictiveDetector,
    IncidentPrediction,
    PredictionSeverity,
)
```

**Add to __all__ List:**
```python
    # Tenant Management
    'TenantManager',
    'TenantConfig',
    'TenantAwareOrchestrator',
    'TenantAwareGraphStorage',
    'get_tenant_manager',
    'set_tenant_context',
    'get_tenant_context',
    'set_user_context',
    'get_user_context',

    # Audit Logging
    'AuditLogger',
    'AuditEvent',
    'AuditEventType',
    'AuditLevel',
    'get_audit_logger',
    'set_audit_logger',

    # PII Scrubbing
    'PIIScrubber',
    'get_pii_scrubber',
    'set_pii_scrubber',

    # Knowledge Base
    'KnowledgeBase',
    'KnowledgeEntry',
    'RAGEnhancedOrchestrator',

    # Auto-Remediation
    'AutoRemediationEngine',
    'RemediationPlan',
    'RemediationAction',
    'RemediationResult',
    'get_remediation_engine',
    'SafetyCheck',

    # Predictive Detection
    'PredictiveDetector',
    'IncidentPrediction',
    'PredictionSeverity',
```

---

### 4. Fix: Add V3 Configuration Options to ADAPTConfig
**File:** `/home/user/ADAPT/core/config.py`
**Lines:** 28-36 (add before to_dict method)

**Add After Line 36:**
```python
    # V3 Features - Tenant Management
    multi_tenancy_enabled: bool = False
    tenant_isolation_enforcement: str = 'strict'  # strict, lenient

    # V3 Features - Audit
    audit_enabled: bool = True
    audit_storage_backend: str = 'memory'  # memory, postgresql
    audit_storage_config: Dict[str, Any] = field(default_factory=dict)
    audit_retention_days: int = 90

    # V3 Features - PII Protection
    pii_scrubbing_enabled: bool = True
    pii_scrub_signals: bool = True
    pii_scrub_results: bool = True
    pii_hash_instead_of_redact: bool = False
    pii_patterns_config: Dict[str, Any] = field(default_factory=dict)

    # V3 Features - Knowledge Base
    knowledge_base_enabled: bool = False
    knowledge_base_persist_dir: str = './data/knowledge'
    knowledge_base_embedding_model: str = 'all-MiniLM-L6-v2'

    # V3 Features - Auto-Remediation
    auto_remediation_enabled: bool = False
    auto_remediation_auto_approve_low_risk: bool = True
    auto_remediation_max_concurrent_actions: int = 3
    auto_remediation_default_timeout: int = 300

    # V3 Features - Predictive Detection
    predictive_detection_enabled: bool = False
    prediction_window_hours: int = 1
    prediction_min_confidence: float = 0.6

    # V3 Features - LLM
    llm_enabled: bool = False
    llm_provider: str = 'anthropic'
    llm_model: str = 'claude-3-5-sonnet-20241022'
    llm_api_key_secret: str = 'llm-api-key'
```

**Also Update to_dict() Method (Around Line 38-50):**
Add all new fields to the returned dictionary.

---

### 5. Fix: Add Missing Imports to API Routes
**File:** `/home/user/ADAPT/api/routes/rca.py`
**Lines:** 1-31

**Add After Existing Imports (Line 31):**
```python
# V3 Features
from core.tenant import (
    get_tenant_manager,
    TenantAwareOrchestrator,
    set_tenant_context,
    get_tenant_context,
)
from core.audit import (
    get_audit_logger,
    AuditEventType,
    AuditLevel,
)
from core.pii_scrubber import get_pii_scrubber
from core.knowledge_base import KnowledgeBase
from core.auto_remediation import get_remediation_engine
from core.predictive_detection import PredictiveDetector
```

---

### 6. Fix: Add Tenant Isolation to RCA Routes
**File:** `/home/user/ADAPT/api/routes/rca.py`
**Location:** `analyze_incident()` function (Lines 71-175)

**Add At Top of Function (After Line 80):**
```python
    # Extract tenant ID from request or use default
    tenant_id = request.metadata.get('tenant_id', 'default') if hasattr(request, 'metadata') else 'default'
    
    # Set tenant context
    from core.tenant import set_tenant_context
    set_tenant_context(tenant_id)
    
    # Check tenant quota
    tenant_manager = get_tenant_manager()
    if not tenant_manager.check_quota(tenant_id, 'concurrent_rca'):
        raise HTTPException(
            status_code=429,
            detail=f"Tenant {tenant_id} has exceeded concurrent RCA quota"
        )
    
    # Increment active RCA count
    tenant_manager.increment_usage(tenant_id, 'active_rcas')
```

**Add Before orchestrator.run_rca() (Line 91):**
```python
    # Use tenant-aware orchestrator
    base_orchestrator = orchestrator
    tenant_orch = TenantAwareOrchestrator(base_orchestrator, tenant_manager)
```

**Replace orchestrator call (Line 91-93) with:**
```python
    context = await tenant_orch.run_rca(
        tenant_id=tenant_id,
        incident_id=request.incident_id,
        signals=signals
    )
```

**Add Audit Logging (Line 95):**
```python
    # Log RCA initiation
    audit_logger = get_audit_logger()
    await audit_logger.log_event(
        event_type=AuditEventType.RCA_STARTED,
        action="analyze_incident",
        resource_type="incident",
        resource_id=request.incident_id,
        result="started",
        details={"user": user.username, "tenant_id": tenant_id}
    )
```

**Add PII Scrubbing (Before Line 83):**
```python
    # Scrub PII from signals
    if orchestrator.config.pii_scrubbing_enabled:
        pii_scrubber = get_pii_scrubber()
        signals = [pii_scrubber.scrub_signal(s) for s in signals]
```

**Add At End of Function (Before Return, Line 160):**
```python
    # Log RCA completion
    await audit_logger.log_event(
        event_type=AuditEventType.RCA_COMPLETED,
        action="analyze_incident",
        resource_type="incident",
        resource_id=request.incident_id,
        result="success",
        details={"duration_seconds": execution_time, "tenant_id": tenant_id}
    )
    
    # Decrement active RCA count
    tenant_manager.decrement_usage(tenant_id, 'active_rcas')
```

**Add PII Scrubbing Before Return:**
```python
    # Scrub results before returning
    if orchestrator.config.pii_scrubbing_enabled:
        pii_scrubber = get_pii_scrubber()
        # Scrub findings
        all_findings = [pii_scrubber.scrub_dict(f.dict()) for f in all_findings]
        # Scrub narrative
        narrative = pii_scrubber.scrub_text(context.graph.export_narrative())
```

---

### 7. Fix: Add Tenant Isolation to Incidents Routes
**File:** `/home/user/ADAPT/api/routes/incidents.py`
**Lines:** 31-36

**Replace List Graphs Call (Line 35-37):**
```python
    from core.tenant import TenantAwareGraphStorage, get_tenant_context
    
    tenant_id = get_tenant_context() or "default"
    
    base_storage = get_graph_storage()
    storage = TenantAwareGraphStorage(base_storage)
    
    graphs = await storage.list_graphs(
        tenant_id=tenant_id,  # Add tenant_id parameter
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
```

**Similar Fix Needed in delete_incident() (Line 88):**
```python
    # Check tenant ownership before deleting
    from core.tenant import TenantAwareGraphStorage, get_tenant_context
    
    tenant_id = get_tenant_context() or "default"
    base_storage = get_graph_storage()
    storage = TenantAwareGraphStorage(base_storage)
    
    # Verify incident belongs to tenant
    graph = await storage.load_graph(incident_id, tenant_id=tenant_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Incident not found")
```

---

### 8. Fix: Add Audit Logging to Agents
**File:** `/home/user/ADAPT/agents/base.py`
**Location:** BaseAgent.execute() method

**Add Import at Top:**
```python
from core.audit import get_audit_logger, AuditEventType
```

**Wrap execute() in Decorator (or Add Manual Logging):**
```python
    @abstractmethod
    async def execute(self, context: Any) -> AgentResult:
        """Execute the agent's diagnostic logic."""
        
        # Log agent execution
        audit_logger = get_audit_logger()
        
        try:
            # ... execute logic ...
            result = await self._execute_impl(context)
            
            await audit_logger.log_event(
                event_type=AuditEventType.AGENT_EXECUTED,
                action=f"execute_{self.name}",
                resource_type="agent",
                resource_id=self.name,
                result="success",
                details={
                    "incident_id": context.incident_id,
                    "findings_count": len(result.findings)
                }
            )
            
            return result
            
        except Exception as e:
            await audit_logger.log_event(
                event_type=AuditEventType.RCA_FAILED,
                action=f"execute_{self.name}",
                resource_type="agent",
                resource_id=self.name,
                result="failure",
                details={"error": str(e)}
            )
            raise
```

---

### 9. Fix: Add Missing Audit Event Type Enum
**File:** `/home/user/ADAPT/core/audit.py`
**Location:** Add after line 68 in AuditEventType

```python
    # Agent Execution (if adding agent tracking)
    AGENT_EXECUTED = "agent.executed"
    AGENT_FAILED = "agent.failed"
```

---

## Files That Need Changes - Priority Order

### CRITICAL (Will Crash):
1. `/home/user/ADAPT/core/auto_remediation.py` - Add Tuple import
2. `/home/user/ADAPT/core/audit.py` - Add audit event types

### HIGH (Missing Core Functionality):
3. `/home/user/ADAPT/core/__init__.py` - Export v3 modules
4. `/home/user/ADAPT/core/config.py` - Add v3 config
5. `/home/user/ADAPT/api/routes/rca.py` - Add imports, security, logging
6. `/home/user/ADAPT/api/routes/incidents.py` - Add tenant isolation
7. `/home/user/ADAPT/agents/base.py` - Add audit logging

### MEDIUM (Additional Features):
8. `/home/user/ADAPT/core/orchestrator.py` - Integrate v3 features
9. `/home/user/ADAPT/api/routes/` - Create new endpoints for v3 features
10. `/home/user/ADAPT/core/audit.py` - Implement PostgreSQL storage

---

## Testing Checklist

After implementing fixes:

- [ ] `pytest tests/test_auto_remediation.py` - Verify Tuple import fix
- [ ] `pytest tests/test_audit.py` - Verify audit event types
- [ ] Run API with `python api/server.py` - No import errors
- [ ] Test `/api/v1/rca/analyze` - Verify tenant isolation
- [ ] Test `/api/v1/incidents` - Verify tenant filtering
- [ ] Check logs contain audit events
- [ ] Verify PII scrubbed in responses

