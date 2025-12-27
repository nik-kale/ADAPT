# LLM Integration Guide

ADAPT supports multiple LLM providers for AI-powered root cause analysis. This guide explains how to configure and use LLM integration.

## Supported Providers

- **Anthropic Claude** (claude-3-5-sonnet, claude-3-opus, claude-3-haiku)
- **OpenAI GPT** (gpt-4, gpt-4-turbo, gpt-3.5-turbo)
- **Local Models** (Ollama, LM Studio, any OpenAI-compatible API)

## Quick Start

### 1. Install LLM Dependencies

```bash
pip install adapt-framework[llm]
```

### 2. Configure API Keys

```bash
# For Anthropic Claude
export ANTHROPIC_API_KEY=sk-ant-xxx

# For OpenAI
export OPENAI_API_KEY=sk-xxx
```

### 3. Enable in Configuration

**config.yaml:**
```yaml
llm_enabled: true
llm_provider: anthropic  # or 'openai'
llm_model: claude-3-5-sonnet-20241022
llm_max_tokens: 4096
```

## Configuration Options

### Full Configuration Example

```yaml
# Enable LLM integration
llm_enabled: true

# Provider selection
llm_provider: anthropic  # Options: 'anthropic', 'openai'

# Model selection
llm_model: claude-3-5-sonnet-20241022

# API key environment variable name
llm_api_key_env: ANTHROPIC_API_KEY

# Maximum tokens for responses
llm_max_tokens: 4096

# Optional: Temperature for creativity (0.0-1.0)
# Lower = more deterministic, Higher = more creative
# Default is handled by the provider
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-xxx` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-xxx` |
| `ADAPT_LLM_PROVIDER` | Override provider in config | `anthropic` |
| `ADAPT_LLM_MODEL` | Override model in config | `gpt-4-turbo` |

## Usage Examples

### Python API

#### Basic Usage

```python
from core import RCAOrchestrator, ADAPTConfig, load_config
from agents.llm_providers import AnthropicProvider, set_llm_provider

# Load configuration
config = load_config('config.yaml')

# Initialize LLM provider
llm = AnthropicProvider(
    api_key=None,  # Uses ANTHROPIC_API_KEY env var
    model="claude-3-5-sonnet-20241022"
)
set_llm_provider(llm)

# Use orchestrator with LLM-enhanced agents
orchestrator = RCAOrchestrator(config)
# ... register agents and run RCA
```

#### Direct LLM Usage

```python
import asyncio
from agents.llm_providers import AnthropicProvider, OpenAIProvider

async def analyze_with_llm():
    # Use Anthropic Claude
    claude = AnthropicProvider()

    response = await claude.complete_with_system(
        system_prompt="You are an expert SRE analyzing system logs.",
        user_prompt="Analyze these error logs and identify the root cause:\n..."
    )

    print(response)

asyncio.run(analyze_with_llm())
```

#### Switching Providers

```python
from agents.llm_providers import AnthropicProvider, OpenAIProvider, set_llm_provider

# Use Claude
claude = AnthropicProvider(model="claude-3-5-sonnet-20241022")
set_llm_provider(claude)

# Switch to GPT-4
gpt4 = OpenAIProvider(model="gpt-4-turbo")
set_llm_provider(gpt4)
```

### CLI Usage

```bash
# Run analysis with LLM enabled
adapt analyze \
    --incident-dir ./incidents/latency-spike \
    --config config.yaml \
    --output ./results

# Override LLM provider via environment
ADAPT_LLM_PROVIDER=openai \
ADAPT_LLM_MODEL=gpt-4-turbo \
adapt analyze --incident-dir ./incidents/auth-failure
```

## Provider-Specific Configuration

### Anthropic Claude

```python
from agents.llm_providers import AnthropicProvider

provider = AnthropicProvider(
    api_key="sk-ant-xxx",  # Or use env var
    model="claude-3-5-sonnet-20241022"  # Latest model
)

# Available models:
# - claude-3-5-sonnet-20241022 (recommended)
# - claude-3-opus-20240229 (most capable)
# - claude-3-haiku-20240307 (fastest, cheapest)
```

### OpenAI GPT

```python
from agents.llm_providers import OpenAIProvider

provider = OpenAIProvider(
    api_key="sk-xxx",  # Or use env var
    model="gpt-4-turbo"
)

# Available models:
# - gpt-4-turbo (recommended)
# - gpt-4 (most capable, slower)
# - gpt-3.5-turbo (fastest, cheapest)
```

### Local Models (Ollama)

```python
from agents.llm_providers import LocalLLMProvider

provider = LocalLLMProvider(
    base_url="http://localhost:11434/v1",  # Ollama default
    model="llama2"
)

# Available models (depends on what you've pulled):
# - llama2
# - codellama
# - mistral
# - mixtral
```

## Advanced Usage

### Custom Temperature and Parameters

```python
provider = AnthropicProvider()

response = await provider.complete(
    prompt="Your question here",
    max_tokens=2000,
    temperature=0.3  # Lower for more focused answers
)
```

### Streaming Responses (Future Enhancement)

```python
# Coming soon: Streaming support for real-time analysis
async for chunk in provider.complete_streaming(prompt):
    print(chunk, end='', flush=True)
```

### Error Handling

```python
from agents.llm_providers import AnthropicProvider

provider = AnthropicProvider()

try:
    response = await provider.complete("Analyze this incident...")
except ImportError:
    print("Install anthropic: pip install anthropic")
except Exception as e:
    print(f"LLM error: {e}")
    # Fallback to heuristic analysis
```

## Integration with ADAPT Agents

### LLM-Enhanced Agents

ADAPT includes LLM-enhanced versions of core agents in `agents/llm_enhanced_agents.py`:

```python
from agents.llm_enhanced_agents import (
    LLMEnhancedLogAnalyzer,
    LLMEnhancedMetricAnalyzer,
    LLMEnhancedChangeCorrelator
)

# Use LLM-enhanced agents
orchestrator.register_agent('log_analyzer', LLMEnhancedLogAnalyzer())
orchestrator.register_agent('metric_analyzer', LLMEnhancedMetricAnalyzer())
orchestrator.register_agent('change_correlator', LLMEnhancedChangeCorrelator())
```

### Custom LLM Integration

Create custom agents with LLM support:

```python
from agents.base import BaseAgent, AgentResult
from agents.llm_providers import get_llm_provider
from core import OrchestrationContext

class CustomLLMAgent(BaseAgent):
    async def execute(self, context: OrchestrationContext) -> AgentResult:
        llm = get_llm_provider()

        if llm is None:
            # Fallback to non-LLM logic
            return self._heuristic_analysis(context)

        # Build prompt from context
        prompt = self._build_prompt(context)

        # Get LLM analysis
        response = await llm.complete_with_system(
            system_prompt="You are an expert in system diagnostics.",
            user_prompt=prompt
        )

        # Parse and return results
        return self._parse_llm_response(response, context)
```

## Cost Optimization

### Model Selection

| Provider | Model | Cost (input/output per 1M tokens) | Best For |
|----------|-------|----------------------------------|----------|
| Anthropic | Claude 3.5 Sonnet | $3/$15 | Balanced performance |
| Anthropic | Claude 3 Opus | $15/$75 | Complex analysis |
| Anthropic | Claude 3 Haiku | $0.25/$1.25 | High-volume, simple tasks |
| OpenAI | GPT-4 Turbo | $10/$30 | Complex reasoning |
| OpenAI | GPT-3.5 Turbo | $0.50/$1.50 | Simple tasks |
| Local | Ollama (free) | Free | Development, testing |

### Token Management

```python
# Limit max tokens to control costs
provider = AnthropicProvider()

response = await provider.complete(
    prompt=long_prompt,
    max_tokens=1000  # Limit response length
)
```

### Caching (Anthropic)

Anthropic supports prompt caching for repeated prefixes:

```python
# Use system prompts that stay constant
# Anthropic will cache them automatically
response = await provider.complete_with_system(
    system_prompt="[Long, constant system instructions]",
    user_prompt="[Variable user content]"
)
# Subsequent calls reuse cached system prompt
```

## Troubleshooting

### API Key Not Found

```
Error: anthropic_api_key must be provided or ANTHROPIC_API_KEY environment variable must be set
```

**Solution:**
```bash
export ANTHROPIC_API_KEY=sk-ant-xxx
```

### Module Not Found

```
ModuleNotFoundError: No module named 'anthropic'
```

**Solution:**
```bash
pip install adapt-framework[llm]
# Or directly:
pip install anthropic openai
```

### Rate Limiting

```
RateLimitError: You have exceeded your rate limit
```

**Solution:**
- Reduce concurrent requests
- Upgrade API plan
- Add retry logic with exponential backoff

### Context Length Exceeded

```
Error: Request too large (context length exceeded)
```

**Solution:**
```python
# Truncate input or use smaller model
response = await provider.complete(
    prompt=truncated_prompt,
    max_tokens=2000  # Reduce if needed
)
```

## Best Practices

1. **Use Environment Variables**: Never hardcode API keys
2. **Set Appropriate Timeouts**: LLM calls can take 5-30 seconds
3. **Implement Fallbacks**: Handle LLM failures gracefully
4. **Monitor Costs**: Track token usage and API costs
5. **Choose Right Model**: Balance cost vs. capability
6. **Cache When Possible**: Reuse results for similar queries
7. **Validate Responses**: Always validate LLM output

## Performance Considerations

### Response Times

- **Claude 3.5 Sonnet**: 2-10 seconds typical
- **Claude 3 Haiku**: 1-3 seconds typical
- **GPT-4 Turbo**: 3-15 seconds typical
- **Local Models**: 5-30 seconds (depends on hardware)

### Concurrent Requests

```python
import asyncio
from agents.llm_providers import AnthropicProvider

provider = AnthropicProvider()

# Process multiple analyses concurrently
async def analyze_multiple(prompts):
    tasks = [provider.complete(p) for p in prompts]
    return await asyncio.gather(*tasks)
```

## Examples

See the `examples/llm_integration/` directory for complete examples:

- `basic_usage.py` - Simple LLM integration
- `agent_integration.py` - LLM-enhanced agents
- `cost_optimization.py` - Token management
- `error_handling.py` - Robust error handling
- `local_models.py` - Using Ollama/local models

## Further Reading

- [Anthropic Claude Documentation](https://docs.anthropic.com/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Ollama Documentation](https://ollama.ai/docs)
- [ADAPT Architecture](architecture.md)

