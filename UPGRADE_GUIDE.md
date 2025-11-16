# ADAPT v1.0 → v2.0 Upgrade Guide

This guide covers the major improvements added to ADAPT v2.0 and how to upgrade from v1.0.

## 🎉 What's New in v2.0

### 1. Production-Ready Infrastructure

**Error Handling & Validation**
- Added comprehensive input validation (`core/validators.py`)
- Better error messages and recovery
- Validation for signals, graph nodes, and configuration

**Structured Logging & Observability**
- JSON-formatted logging (`core/observability.py`)
- Distributed tracing with trace IDs
- Better log aggregation support

**Metrics Collection**
- Performance metrics tracking (`core/metrics.py`)
- Agent execution statistics
- Prometheus metrics export

### 2. Performance Improvements

**Caching Layer**
- In-memory caching with TTL (`core/cache.py`)
- Decorator-based caching for functions
- LRU eviction policy

**Parallel Processing**
- Async batch processing (`core/parallel.py`)
- Thread and process pool support
- Configurable concurrency limits

### 3. Security Enhancements

**Secrets Management**
- Abstract secret provider interface (`core/secrets.py`)
- Support for AWS Secrets Manager, HashiCorp Vault
- Environment variable fallback

### 4. Operational Features

**Health Monitoring**
- Component health checks (`core/health.py`)
- Health status API
- Monitoring integration support

### 5. LLM Integration

**LLM Providers**
- Anthropic Claude integration (`agents/llm_providers.py`)
- OpenAI GPT support
- Local LLM support (Ollama, LM Studio)

## 📦 Installation

### Upgrading from v1.0

```bash
# Pull latest code
git pull origin main

# Install new dependencies
pip install -r requirements.txt --upgrade

# Or install specific feature sets
pip install -e ".[llm]"      # LLM integration
pip install -e ".[cloud]"    # Cloud providers
pip install -e ".[all]"      # Everything
```

### Fresh Installation

```bash
git clone https://github.com/yourusername/ADAPT.git
cd ADAPT
pip install -r requirements.txt
```

## 🔧 Configuration Changes

### New Configuration Options

Update your `config.yaml` with new options:

```yaml
# Logging configuration
log_level: INFO
json_logging: true  # Enable structured JSON logs

# Caching
cache:
  enabled: true
  max_size: 1000
  default_ttl_seconds: 300

# Metrics
metrics:
  enabled: true
  export_prometheus: true

# Secrets
secrets:
  provider: environment  # or 'aws', 'vault'
  # AWS Secrets Manager
  aws:
    region: us-west-2
  # HashiCorp Vault
  vault:
    url: https://vault.example.com
    mount_point: secret

# LLM
llm:
  provider: anthropic  # or 'openai', 'local'
  model: claude-3-5-sonnet-20241022
  # API keys should be in secrets, not config!

# Health checks
health:
  enabled: true
  check_interval_seconds: 60
```

## 🚀 Usage Examples

### Using Structured Logging

```python
from core.observability import StructuredLogger, TracingContext

logger = StructuredLogger(__name__)

with TracingContext("rca_analysis"):
    logger.info("Starting RCA", incident_id="inc_001")
    # ... your code ...
    logger.info("RCA completed", duration_seconds=45.2)
```

### Using Caching

```python
from core.cache import cached

@cached(ttl_seconds=60)
async def fetch_expensive_data(param1, param2):
    # This result will be cached for 60 seconds
    return expensive_operation(param1, param2)
```

### Using LLM Integration

```python
from agents.llm_providers import AnthropicProvider, set_llm_provider

# Initialize LLM provider
llm = AnthropicProvider(api_key="your-api-key")
set_llm_provider(llm)

# Use in agents
response = await llm.complete("Analyze these error logs...")
```

### Using Secrets Management

```python
from core.secrets import set_secret_provider, AWSSecretsManagerProvider

# Use AWS Secrets Manager
secrets = AWSSecretsManagerProvider(region='us-west-2')
set_secret_provider(secrets)

# Get secrets
api_key = secrets.get_secret('adapt/api-key')
```

### Using Health Checks

```python
from core.health import get_health_monitor

monitor = get_health_monitor()
checks = await monitor.check_health()
summary = monitor.get_health_summary()

print(f"Overall status: {summary['status']}")
```

### Using Metrics

```python
from core.metrics import get_metrics_collector

collector = get_metrics_collector()

# Metrics are collected automatically, but you can add custom ones
collector.record_agent_execution('my_agent', duration=1.5, success=True)

# Get stats
stats = collector.get_overall_stats()

# Export for Prometheus
prometheus_metrics = collector.export_prometheus_metrics()
```

## 🔄 Migration Guide

### For Custom Agents

**Before (v1.0):**
```python
class MyAgent(BaseAgent):
    async def execute(self, context):
        # ... logic ...
        return AgentResult(agent_name=self.name, findings=findings)
```

**After (v2.0) - with improvements:**
```python
from core.observability import StructuredLogger, TracingContext
from core.validators import ValidationError

class MyAgent(BaseAgent):
    def __init__(self, config=None):
        super().__init__(name='my_agent', config=config)
        self.logger = StructuredLogger(__name__)

    async def execute(self, context):
        with TracingContext(f"agent_{self.name}"):
            self.logger.info("Agent starting", context_id=context.incident_id)

            try:
                # ... logic ...

                self.logger.info("Agent completed", findings_count=len(findings))
                return AgentResult(agent_name=self.name, findings=findings)

            except Exception as e:
                self.logger.error("Agent failed", error=str(e))
                raise
```

### For Custom Connectors

**Enhanced with caching:**
```python
from core.cache import cached

class MyConnector(BaseConnector):
    @cached(ttl_seconds=60)
    async def fetch_logs(self, start_time, end_time, filters=None):
        # Results cached for 60 seconds
        return await self._fetch_from_source(start_time, end_time)
```

## 🔒 Security Best Practices

1. **Never commit API keys**
   - Use environment variables or secret managers
   - Add `.env` to `.gitignore`

2. **Use secrets management**
   - Store credentials in AWS Secrets Manager or Vault
   - Rotate secrets regularly

3. **Enable validation**
   - Always validate input signals
   - Check configuration on startup

4. **Monitor health**
   - Set up health check endpoints
   - Alert on degraded status

## 📊 Monitoring in Production

### Prometheus Integration

```python
from fastapi import FastAPI
from core.metrics import get_metrics_collector
from core.health import get_health_monitor

app = FastAPI()

@app.get("/metrics")
async def metrics():
    collector = get_metrics_collector()
    return collector.export_prometheus_metrics()

@app.get("/health")
async def health():
    monitor = get_health_monitor()
    await monitor.check_health()
    return monitor.get_health_summary()
```

### Logging to ELK/Splunk

Configure JSON logging and ship to your log aggregator:

```python
from core.observability import configure_logging

# Enable JSON logging
configure_logging(level='INFO', json_format=True)
```

## ⚠️ Breaking Changes

None! v2.0 is fully backward compatible with v1.0.

All new features are opt-in:
- Existing code continues to work without modifications
- New features are available when you explicitly use them
- Default behavior unchanged

## 🐛 Troubleshooting

### Import Errors

**Problem:** `ImportError: cannot import name 'StructuredLogger'`

**Solution:** Make sure you've upgraded to v2.0:
```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

### Missing Dependencies

**Problem:** `ModuleNotFoundError: No module named 'anthropic'`

**Solution:** Install optional dependencies:
```bash
pip install anthropic  # For LLM integration
pip install boto3      # For AWS
pip install hvac       # For Vault
```

## 📚 Additional Resources

- [Architecture Documentation](docs/architecture.md)
- [Component Catalog](docs/component-catalog.md)
- [API Reference](docs/api-reference.md)
- [Examples](examples/)

## 💬 Getting Help

- GitHub Issues: https://github.com/yourusername/ADAPT/issues
- Discussions: https://github.com/yourusername/ADAPT/discussions
- Email: adapt-framework@example.com

## 🎯 Next Steps

1. Review the new configuration options
2. Enable structured logging
3. Set up health monitoring
4. Try LLM-powered agents
5. Configure secrets management

Happy upgrading! 🚀
