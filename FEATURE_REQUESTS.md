# ADAPT Repository Feature Discovery Analysis

**Generated**: 2025-12-26
**Repository**: ADAPT (Agentic Diagnostics & Proactive Troubleshooting)
**Current Version**: v5.0.0-alpha
**Analyzed by**: Senior Software Architect Review

---

## Summary Table

| # | Feature | Category | Effort | Value | Priority Score |
|---|---------|----------|--------|-------|----------------|
| 1 | Unify Version Strings Across Codebase | Code Quality | Low | High | 3.0 |
| 2 | Add API Endpoint Test Suite | Testing/DX | Medium | High | 1.5 |
| 3 | Implement Retry Logic with Exponential Backoff | Reliability | Medium | High | 1.5 |
| 4 | Add Circuit Breaker Pattern for External Services | Architecture | Medium | High | 1.5 |
| 5 | Enhance Structured Logging with Correlation IDs | Observability | Low | Medium | 2.0 |
| 6 | Add Prometheus Metrics for Connection Pools | Observability | Low | Medium | 2.0 |
| 7 | Implement PostgreSQL Audit Storage Backend | Functional | High | Medium | 0.67 |
| 8 | Add Rate Limiter & Middleware Test Coverage | Testing/Security | Low | Medium | 2.0 |
| 9 | Replace Bare Exception Handlers with Specific Types | Code Quality | Medium | Medium | 1.0 |
| 10 | Add OpenAPI Schema Validation Tests | Testing/DX | Low | Low | 1.0 |

---

## Detailed Feature Requests

---

### Feature #1: Unify Version Strings Across Codebase

**Category**: Code Quality & Maintenance

**Problem Statement**:
The codebase has inconsistent version strings scattered across multiple files. Currently found:
- `__init__.py`: `__version__ = '1.0.0'`
- `api/server.py`: FastAPI `version="4.0.0"` and endpoint returns `"version": "3.0.0"`
- `cli/main.py`: `@click.version_option(version='2.0.0')` and displays "v2.0"

This creates confusion for users checking versions and makes release management error-prone.

**Proposed Solution**:
- Create a single source of truth: `ADAPT/__version__.py` or update `__init__.py`
- Import version from this canonical location in all other files
- Update CI/CD to validate version consistency during releases
- Add a `bump-version` script or use a tool like `bumpversion`/`python-semantic-release`

```python
# core/version.py
__version__ = "5.0.0"
VERSION_INFO = {
    "version": __version__,
    "api_version": "v1",
    "platform": "ADAPT",
}
```

**Impact Assessment**:
- **Effort**: Low (1-2 hours)
- **Value**: High (reduces release errors, improves user experience)
- **Priority Score**: 3.0 (High/Low)

**Success Metrics**:
- Single version string referenced in all locations
- CI check validates version consistency
- Users report correct version via CLI, API, and imports

---

### Feature #2: Add API Endpoint Test Suite

**Category**: Testing & Developer Experience

**Problem Statement**:
The API layer (`api/server.py`, `api/routes/*.py`) has no dedicated test coverage. While integration tests exist for core components, there are no tests for:
- HTTP status codes and response formats
- Authentication/authorization flows
- Rate limiting behavior
- Error response structures
- Request validation

This creates risk of API regressions going undetected.

**Proposed Solution**:
- Create `tests/test_api/` directory with dedicated test modules:
  - `test_api_auth.py` - JWT/API key authentication
  - `test_api_rca.py` - RCA endpoint tests
  - `test_api_incidents.py` - Incident CRUD tests
  - `test_api_health.py` - Health/metrics endpoint tests
- Use `httpx.AsyncClient` with `TestClient` for FastAPI testing
- Add fixtures for authenticated/unauthenticated requests
- Test both success and error paths

```python
# tests/test_api/test_api_health.py
import pytest
from httpx import AsyncClient
from api.server import app

@pytest.mark.asyncio
async def test_health_endpoint_returns_200():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert "status" in response.json()
```

**Impact Assessment**:
- **Effort**: Medium (2-3 days)
- **Value**: High (prevents API regressions, improves confidence)
- **Priority Score**: 1.5 (High/Medium)

**Success Metrics**:
- 80%+ API endpoint coverage
- All routes have at least success/error path tests
- CI runs API tests on every PR

---

### Feature #3: Implement Retry Logic with Exponential Backoff

**Category**: Reliability & Architecture

**Problem Statement**:
External connectors (`prometheus_connector.py`, `elasticsearch_connector.py`) and integrations (`github.py`, `jira.py`, `slack.py`) lack retry logic for transient failures. A single network timeout or 503 response causes immediate failure, even when a retry would likely succeed.

Current pattern observed:
```python
try:
    response = await self.session.get(url)
except Exception as e:
    logger.error(f"Failed to fetch: {e}")
    return []  # No retry
```

**Proposed Solution**:
- Create a reusable retry decorator/utility in `core/retry.py`
- Implement exponential backoff with jitter
- Configure retry behavior per-connector (max attempts, backoff factor)
- Add circuit breaker integration (see Feature #4)
- Log retry attempts with context

```python
# core/retry.py
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import aiohttp

def with_retry(max_attempts: int = 3, backoff_factor: float = 1.0):
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=backoff_factor, min=1, max=30),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retry {retry_state.attempt_number}/{max_attempts}: {retry_state.outcome}"
        )
    )
```

**Impact Assessment**:
- **Effort**: Medium (1-2 days)
- **Value**: High (significantly improves reliability)
- **Priority Score**: 1.5 (High/Medium)

**Success Metrics**:
- 90%+ success rate for transient failures (vs current ~0%)
- Measurable reduction in failed RCAs due to connector errors
- Retry metrics visible in observability stack

---

### Feature #4: Add Circuit Breaker Pattern for External Services

**Category**: Architecture & Scalability

**Problem Statement**:
When external services (Prometheus, Elasticsearch, GitHub, Jira) are down or degraded, ADAPT continues sending requests, potentially:
- Exhausting connection pools
- Adding load to already-struggling services
- Causing cascading failures
- Wasting resources on requests that will fail

**Proposed Solution**:
- Implement circuit breaker using `pybreaker` or custom implementation
- Add per-service circuit state: CLOSED (normal), OPEN (failing), HALF-OPEN (testing)
- Expose circuit state in health checks and metrics
- Configure thresholds per service (failure count, recovery time)

```python
# core/circuit_breaker.py
from pybreaker import CircuitBreaker

prometheus_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    listeners=[CircuitBreakerMetricsListener()]
)

# In connector
@prometheus_breaker
async def query_prometheus(self, query: str):
    return await self._execute_query(query)
```

**Impact Assessment**:
- **Effort**: Medium (1-2 days)
- **Value**: High (prevents cascade failures, improves resilience)
- **Priority Score**: 1.5 (High/Medium)

**Success Metrics**:
- Circuit breaker trips prevent >90% of requests to failing services
- Mean time to recovery improves after external service restoration
- Health endpoint shows circuit states

---

### Feature #5: Enhance Structured Logging with Correlation IDs

**Category**: Observability Stack

**Problem Statement**:
While `RequestIDMiddleware` adds request IDs to responses, log messages don't consistently include these IDs. Tracing a request through the system requires manual correlation. Current logging is basic:
```python
logger.info(f"Starting RCA for incident: {incident_id}")
# Missing: request_id, user_id, tenant_id
```

**Proposed Solution**:
- Create a logging context manager that propagates correlation IDs
- Use `contextvars` to store request context
- Update all loggers to include structured fields
- Add log format that outputs JSON with standard fields

```python
# core/logging_context.py
import contextvars
import logging

request_context: contextvars.ContextVar[dict] = contextvars.ContextVar('request_context')

class ContextualLogger(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        ctx = request_context.get({})
        extra = {
            'request_id': ctx.get('request_id'),
            'tenant_id': ctx.get('tenant_id'),
            'user_id': ctx.get('user_id'),
            **kwargs.get('extra', {})
        }
        return msg, {**kwargs, 'extra': extra}
```

**Impact Assessment**:
- **Effort**: Low (1 day)
- **Value**: Medium (improves debugging, supports distributed tracing)
- **Priority Score**: 2.0 (Medium/Low)

**Success Metrics**:
- 100% of log entries include request_id when in request context
- Ability to filter logs by request/tenant/user in log aggregator
- Reduced mean time to debug issues by 30%+

---

### Feature #6: Add Prometheus Metrics for Connection Pools

**Category**: Observability Stack

**Problem Statement**:
The Prometheus connector uses connection pooling (v4.0 enhancement) but there's no visibility into pool health:
- Active connections
- Available connections
- Wait queue length
- Connection errors
- Pool exhaustion events

Without these metrics, capacity planning and troubleshooting are difficult.

**Proposed Solution**:
- Add Prometheus metrics in `connectors/prometheus_connector.py`
- Expose metrics via `/metrics` endpoint (already exists)
- Track pool lifecycle events

```python
# connectors/prometheus_connector.py
from prometheus_client import Gauge, Counter

pool_active_connections = Gauge(
    'adapt_connector_pool_active',
    'Active connections in pool',
    ['connector', 'host']
)
pool_available_connections = Gauge(
    'adapt_connector_pool_available',
    'Available connections in pool',
    ['connector', 'host']
)
pool_exhaustion_total = Counter(
    'adapt_connector_pool_exhaustion_total',
    'Pool exhaustion events',
    ['connector', 'host']
)
```

**Impact Assessment**:
- **Effort**: Low (4-6 hours)
- **Value**: Medium (enables proactive capacity management)
- **Priority Score**: 2.0 (Medium/Low)

**Success Metrics**:
- Connection pool metrics visible in Grafana/monitoring
- Alerts can be set for pool exhaustion
- Capacity planning based on actual usage patterns

---

### Feature #7: Implement PostgreSQL Audit Storage Backend

**Category**: Functional Enhancement

**Problem Statement**:
The audit system has TODO placeholders for PostgreSQL storage:
```python
# core/audit.py
# TODO: Initialize PostgreSQL connection
# TODO: Implement PostgreSQL storage
# TODO: Implement PostgreSQL query
```

File-based audit storage (current implementation) doesn't scale for:
- Multi-instance deployments
- Complex queries (date ranges, filtering)
- Long-term retention policies
- High-availability requirements

**Proposed Solution**:
- Implement `PostgreSQLAuditBackend` class
- Use connection pooling (asyncpg)
- Add database migration scripts
- Support both file and PostgreSQL backends via config
- Add query capabilities (date range, event type, user, resource)

```python
# core/audit.py
class PostgreSQLAuditBackend(AuditBackend):
    def __init__(self, connection_string: str):
        self.pool = None
        self.connection_string = connection_string

    async def initialize(self):
        self.pool = await asyncpg.create_pool(self.connection_string)

    async def write_event(self, event: AuditEvent):
        async with self.pool.acquire() as conn:
            await conn.execute(
                '''INSERT INTO audit_events
                   (id, timestamp, event_type, user_id, action, resource_id, result, details)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)''',
                event.id, event.timestamp, event.event_type.value, ...
            )
```

**Impact Assessment**:
- **Effort**: High (3-5 days)
- **Value**: Medium (required for enterprise scale)
- **Priority Score**: 0.67 (Medium/High)

**Success Metrics**:
- Audit queries complete in <100ms for 1M+ events
- Support for multi-instance deployments
- Compliance reports generate from PostgreSQL backend

---

### Feature #8: Add Rate Limiter & Middleware Test Coverage

**Category**: Testing & Security

**Problem Statement**:
The security middleware layer (`api/middleware/`) has no test coverage:
- `rate_limit.py` - Rate limiting logic
- `concurrency_limit.py` - Request concurrency limits
- `security_headers.py` - Security header injection
- `request_id.py` - Request ID propagation

These are critical security components that should have thorough testing.

**Proposed Solution**:
- Create `tests/test_middleware/` directory
- Test rate limiting behavior (burst, sustained, by key)
- Test concurrency limits (rejection, queuing)
- Verify security headers are present
- Test request ID generation and propagation

```python
# tests/test_middleware/test_rate_limit.py
import pytest
from api.middleware.rate_limit import RateLimiter

@pytest.mark.asyncio
async def test_rate_limiter_allows_under_limit():
    limiter = RateLimiter(requests_per_minute=10)
    for _ in range(10):
        assert await limiter.is_allowed("test_key")

@pytest.mark.asyncio
async def test_rate_limiter_blocks_over_limit():
    limiter = RateLimiter(requests_per_minute=10)
    for _ in range(10):
        await limiter.is_allowed("test_key")
    assert not await limiter.is_allowed("test_key")
```

**Impact Assessment**:
- **Effort**: Low (1 day)
- **Value**: Medium (ensures security controls work correctly)
- **Priority Score**: 2.0 (Medium/Low)

**Success Metrics**:
- 90%+ coverage for middleware modules
- Rate limiting verified working under load
- Security headers validated in CI

---

### Feature #9: Replace Bare Exception Handlers with Specific Types

**Category**: Code Quality & Optimization

**Problem Statement**:
The codebase has 70+ instances of `except Exception:` which:
- Catches unexpected errors that should propagate
- Makes debugging harder (masks actual error types)
- Can hide programming errors (TypeError, AttributeError)
- Violates Python best practices

Example from codebase:
```python
try:
    response = await self.session.get(url)
except Exception as e:  # Too broad
    logger.error(f"Failed to fetch: {e}")
    return []
```

**Proposed Solution**:
- Audit all `except Exception` blocks
- Replace with specific exceptions:
  - Network: `aiohttp.ClientError`, `asyncio.TimeoutError`
  - Database: `neo4j.exceptions.Neo4jError`, `elasticsearch.exceptions.ElasticsearchException`
  - Auth: `jwt.exceptions.JWTError`
- Keep `except Exception` only at top-level handlers where appropriate
- Add linting rule to prevent new bare exceptions

```python
# Before
except Exception as e:
    logger.error(f"Failed: {e}")

# After
except aiohttp.ClientError as e:
    logger.error(f"HTTP client error: {e}")
except asyncio.TimeoutError:
    logger.error("Request timed out")
except Exception as e:
    logger.exception(f"Unexpected error: {e}")  # Include stack trace
    raise  # Re-raise unexpected errors
```

**Impact Assessment**:
- **Effort**: Medium (2-3 days)
- **Value**: Medium (improves error handling, debugging)
- **Priority Score**: 1.0 (Medium/Medium)

**Success Metrics**:
- <10 bare `except Exception` clauses remaining (top-level only)
- Ruff/pylint rule enforced in CI
- Improved error categorization in logs

---

### Feature #10: Add OpenAPI Schema Validation Tests

**Category**: Testing & Developer Experience

**Problem Statement**:
The FastAPI application generates OpenAPI documentation but there's no validation that:
- Request/response models match actual behavior
- Schema changes don't break backwards compatibility
- Documentation stays in sync with implementation

**Proposed Solution**:
- Add schema snapshot tests using `pytest-snapshot` or similar
- Validate response bodies match declared models
- Add schema diff check to CI (warn on breaking changes)
- Export and version OpenAPI spec

```python
# tests/test_api/test_openapi_schema.py
import pytest
from api.server import app

def test_openapi_schema_snapshot(snapshot):
    schema = app.openapi()
    snapshot.assert_match(schema, 'openapi_schema.json')

@pytest.mark.parametrize("endpoint,method,expected_status", [
    ("/api/v1/health", "GET", 200),
    ("/api/v1/rca", "POST", 200),
])
def test_endpoints_match_schema(endpoint, method, expected_status):
    # Validate endpoint exists in schema
    schema = app.openapi()
    assert endpoint in schema["paths"]
    assert method.lower() in schema["paths"][endpoint]
```

**Impact Assessment**:
- **Effort**: Low (4-6 hours)
- **Value**: Low (nice-to-have, prevents documentation drift)
- **Priority Score**: 1.0 (Low/Low)

**Success Metrics**:
- OpenAPI schema versioned in repository
- CI alerts on schema changes
- API consumers can rely on documented contracts

---

## Additional Recommendations

### Quick Wins (Not Prioritized Above)

1. **Update CLI Version Display**: The CLI shows "v2.0" but codebase is v5.0
2. **Add `py.typed` Marker**: Enable type checking for library users
3. **Add Pre-commit Hooks**: Enforce formatting/linting before commit
4. **Create SECURITY.md**: Document vulnerability reporting process

### Technical Debt Items

1. **PostgreSQL Audit TODOs**: 4 TODO items in `core/audit.py`
2. **Test Coverage**: ~2,200 LOC tests for ~12,900 LOC codebase (~17%)
3. **Type Hints**: Many functions lack complete type annotations
4. **Docstrings**: Inconsistent docstring coverage

### Future Considerations (v6.0+)

Based on the product roadmap, these features align with planned work:
- WebSocket infrastructure for real-time dashboards
- GraphQL API implementation
- Mobile app API endpoints
- SIEM integration connectors

---

## Implementation Priority Order

Based on Priority Score and dependencies:

1. **Feature #1** - Unify Version Strings (Quick win, no dependencies)
2. **Feature #5** - Structured Logging (Foundation for observability)
3. **Feature #6** - Connection Pool Metrics (Low effort, high value)
4. **Feature #8** - Middleware Tests (Security validation)
5. **Feature #3** - Retry Logic (Reliability improvement)
6. **Feature #4** - Circuit Breaker (Depends on #3)
7. **Feature #2** - API Tests (Comprehensive but time-consuming)
8. **Feature #9** - Exception Handling (Code quality)
9. **Feature #10** - OpenAPI Tests (Nice-to-have)
10. **Feature #7** - PostgreSQL Audit (Largest effort, enterprise feature)

---

## Appendix: Files Analyzed

- `api/server.py` - Main API server
- `api/auth.py` - Authentication/authorization
- `api/middleware/*.py` - Security middleware
- `api/routes/*.py` - API endpoint handlers
- `core/orchestrator.py` - RCA orchestration engine
- `core/audit.py` - Audit logging system
- `core/pii_scrubber.py` - PII detection/redaction
- `core/config.py` - Configuration management
- `connectors/*.py` - Data source connectors
- `integrations/*.py` - External service integrations
- `agents/*.py` - Diagnostic agents
- `tests/*.py` - Test suite
- `cli/main.py` - Command-line interface
- `requirements.txt` - Dependencies
- `PRODUCT_ROADMAP_V5_V8.md` - Product roadmap

---

*Generated by automated repository analysis. Review and adapt priorities based on team capacity and business needs.*
