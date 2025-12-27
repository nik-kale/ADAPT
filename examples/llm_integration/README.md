# LLM Integration Examples

This directory contains practical examples demonstrating LLM integration with ADAPT.

## Prerequisites

```bash
# Install LLM dependencies
pip install adapt-framework[llm]

# Set API key
export ANTHROPIC_API_KEY=sk-ant-xxx
# OR
export OPENAI_API_KEY=sk-xxx
```

## Examples

### 1. Basic Usage (`basic_usage.py`)

Simple LLM provider usage for text analysis.

```bash
python basic_usage.py
```

Demonstrates:
- Basic completions with Anthropic and OpenAI
- System prompts for specialized analysis
- Temperature control
- Token limits

### 2. Agent Integration (`agent_integration.py`)

Complete RCA analysis with LLM-enhanced agents.

```bash
python agent_integration.py
```

Demonstrates:
- LLM-enhanced log, metric, and change analysis
- Integration with RCA orchestrator
- Custom LLM-powered agents
- Full incident analysis workflow

## Quick Start

```python
import asyncio
from agents.llm_providers import AnthropicProvider

async def quick_example():
    provider = AnthropicProvider()
    response = await provider.complete(
        "What causes database connection timeouts?"
    )
    print(response)

asyncio.run(quick_example())
```

## See Also

- [LLM Integration Documentation](../../docs/llm-integration.md)
- [Agent Development Guide](../../docs/agent-development.md)
- [Architecture Overview](../../docs/architecture.md)

