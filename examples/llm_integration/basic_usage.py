"""
Basic LLM Integration Example

Demonstrates how to use LLM providers for simple text analysis.
"""

import asyncio
import os
from agents.llm_providers import AnthropicProvider, OpenAIProvider, set_llm_provider


async def basic_anthropic_example():
    """Basic usage with Anthropic Claude"""
    print("=== Anthropic Claude Example ===\n")

    # Initialize provider (uses ANTHROPIC_API_KEY from environment)
    provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")

    # Simple completion
    response = await provider.complete(
        "Explain what causes database connection timeout errors in 2-3 sentences."
    )

    print("Response:")
    print(response)
    print()


async def basic_openai_example():
    """Basic usage with OpenAI GPT"""
    print("=== OpenAI GPT Example ===\n")

    # Initialize provider (uses OPENAI_API_KEY from environment)
    provider = OpenAIProvider(model="gpt-4-turbo")

    # Simple completion
    response = await provider.complete(
        "What are common causes of API rate limiting?"
    )

    print("Response:")
    print(response)
    print()


async def system_prompt_example():
    """Using system prompts for specialized analysis"""
    print("=== System Prompt Example ===\n")

    provider = AnthropicProvider()

    system_prompt = """You are an expert Site Reliability Engineer (SRE) specializing in
    incident analysis. Provide concise, actionable insights based on technical evidence."""

    user_prompt = """Analyze this log pattern:

    2024-01-15 10:23:45 ERROR Connection timeout to database-01
    2024-01-15 10:23:50 ERROR Connection timeout to database-01
    2024-01-15 10:24:02 ERROR Connection timeout to database-01
    2024-01-15 10:25:15 ERROR Connection pool exhausted

    What is the likely root cause?"""

    response = await provider.complete_with_system(
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )

    print("Analysis:")
    print(response)
    print()


async def temperature_example():
    """Demonstrating temperature parameter for creativity control"""
    print("=== Temperature Control Example ===\n")

    provider = AnthropicProvider()

    prompt = "Suggest 3 possible causes for sudden API latency increase"

    # Low temperature (more focused, deterministic)
    print("Low Temperature (0.2) - More focused:")
    response = await provider.complete(prompt, temperature=0.2)
    print(response)
    print()

    # High temperature (more creative, varied)
    print("High Temperature (0.9) - More creative:")
    response = await provider.complete(prompt, temperature=0.9)
    print(response)
    print()


async def token_limit_example():
    """Controlling response length with max_tokens"""
    print("=== Token Limit Example ===\n")

    provider = AnthropicProvider()

    prompt = "Explain the CAP theorem in distributed systems."

    # Short response
    print("Short response (100 tokens):")
    response = await provider.complete(prompt, max_tokens=100)
    print(response)
    print()

    # Longer response
    print("Longer response (500 tokens):")
    response = await provider.complete(prompt, max_tokens=500)
    print(response)
    print()


async def main():
    """Run all examples"""
    # Check for API keys
    if not os.getenv('ANTHROPIC_API_KEY') and not os.getenv('OPENAI_API_KEY'):
        print("ERROR: Please set ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable")
        print("Example: export ANTHROPIC_API_KEY=sk-ant-xxx")
        return

    try:
        if os.getenv('ANTHROPIC_API_KEY'):
            await basic_anthropic_example()
            await system_prompt_example()
            await temperature_example()
            await token_limit_example()

        if os.getenv('OPENAI_API_KEY'):
            await basic_openai_example()

    except ImportError as e:
        print(f"ERROR: {e}")
        print("Install LLM dependencies: pip install adapt-framework[llm]")
    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())

