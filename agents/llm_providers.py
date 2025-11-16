"""
LLM Provider integrations for ADAPT framework.

Provides abstract interfaces and concrete implementations for various
LLM providers (Anthropic Claude, OpenAI GPT, local models, etc.)
"""

from typing import Optional, Dict, Any, List
import os
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    async def complete(self, prompt: str, **kwargs) -> str:
        """
        Get completion from LLM.

        Args:
            prompt: The prompt to send to the LLM
            **kwargs: Additional provider-specific parameters

        Returns:
            The LLM's response as a string
        """
        pass

    @abstractmethod
    async def complete_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> str:
        """
        Get completion with system and user prompts.

        Args:
            system_prompt: System message/instructions
            user_prompt: User message/question
            **kwargs: Additional parameters

        Returns:
            The LLM's response
        """
        pass


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude integration.

    Requires: pip install anthropic
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if None)
            model: Model to use
        """
        try:
            import anthropic
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")

        self.client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ.get('ANTHROPIC_API_KEY')
        )
        self.model = model

    async def complete(self, prompt: str, **kwargs) -> str:
        """Get completion from Claude"""
        response = await self.client.messages.create(
            model=kwargs.get('model', self.model),
            max_tokens=kwargs.get('max_tokens', 4096),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get('temperature', 0.7)
        )
        return response.content[0].text

    async def complete_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> str:
        """Get completion with system prompt"""
        response = await self.client.messages.create(
            model=kwargs.get('model', self.model),
            max_tokens=kwargs.get('max_tokens', 4096),
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=kwargs.get('temperature', 0.7)
        )
        return response.content[0].text


class OpenAIProvider(LLMProvider):
    """
    OpenAI GPT integration.

    Requires: pip install openai
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo-preview"):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (uses OPENAI_API_KEY env var if None)
            model: Model to use
        """
        try:
            import openai
        except ImportError:
            raise ImportError("Install openai: pip install openai")

        self.client = openai.AsyncOpenAI(
            api_key=api_key or os.environ.get('OPENAI_API_KEY')
        )
        self.model = model

    async def complete(self, prompt: str, **kwargs) -> str:
        """Get completion from GPT"""
        response = await self.client.chat.completions.create(
            model=kwargs.get('model', self.model),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=kwargs.get('max_tokens', 4096),
            temperature=kwargs.get('temperature', 0.7)
        )
        return response.choices[0].message.content

    async def complete_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> str:
        """Get completion with system prompt"""
        response = await self.client.chat.completions.create(
            model=kwargs.get('model', self.model),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=kwargs.get('max_tokens', 4096),
            temperature=kwargs.get('temperature', 0.7)
        )
        return response.choices[0].message.content


class LocalLLMProvider(LLMProvider):
    """
    Local LLM integration (e.g., Ollama, LM Studio).

    Requires: pip install openai (uses OpenAI-compatible API)
    """

    def __init__(self, base_url: str, model: str = "llama2"):
        """
        Initialize local LLM provider.

        Args:
            base_url: Base URL for local LLM API
            model: Model name
        """
        try:
            import openai
        except ImportError:
            raise ImportError("Install openai: pip install openai")

        self.client = openai.AsyncOpenAI(
            base_url=base_url,
            api_key="not-needed"  # Local models don't need API key
        )
        self.model = model

    async def complete(self, prompt: str, **kwargs) -> str:
        """Get completion from local LLM"""
        response = await self.client.chat.completions.create(
            model=kwargs.get('model', self.model),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=kwargs.get('max_tokens', 4096),
            temperature=kwargs.get('temperature', 0.7)
        )
        return response.choices[0].message.content

    async def complete_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs
    ) -> str:
        """Get completion with system prompt"""
        response = await self.client.chat.completions.create(
            model=kwargs.get('model', self.model),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=kwargs.get('max_tokens', 4096),
            temperature=kwargs.get('temperature', 0.7)
        )
        return response.choices[0].message.content


# Global LLM provider instance
_llm_provider: Optional[LLMProvider] = None


def set_llm_provider(provider: LLMProvider):
    """
    Set the global LLM provider.

    Args:
        provider: LLM provider to use globally
    """
    global _llm_provider
    _llm_provider = provider


def get_llm_provider() -> Optional[LLMProvider]:
    """
    Get the global LLM provider.

    Returns:
        Global LLM provider or None if not set
    """
    return _llm_provider
