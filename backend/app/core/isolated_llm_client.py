"""
Isolated LLM Client - Wrapper that prevents concurrent streaming conflicts
"""

import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
import structlog

from app.core.llm_client import LLMClient

logger = structlog.get_logger()


class IsolatedLLMClient:
    """
    Wrapper around LLMClient that ensures only one stream is active at a time.

    This prevents concurrent streaming conflicts when multiple components
    (e.g., main agent and ACE learning) use the same underlying model.

    Key features:
    - Serializes all streaming requests with an asyncio.Lock
    - Creates independent LLMClient instance to avoid shared state
    - Preserves full LLMClient API compatibility
    """

    def __init__(
        self,
        provider: str,
        model_name: str,
        base_url: str,
        context_window: int = 8192,
        temperature: float = 0.7
    ):
        """
        Initialize isolated LLM client

        Args:
            provider: Model provider (ollama, vllm, llamacpp)
            model_name: Model identifier
            base_url: Provider base URL
            context_window: Context window size
            temperature: Sampling temperature
        """
        self.client = LLMClient(
            provider=provider,
            model_name=model_name,
            base_url=base_url
        )
        self.context_window = context_window
        self.temperature = temperature
        self._lock = asyncio.Lock()

        logger.info("isolated_llm_client_created",
                   provider=provider,
                   model=model_name)

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        response_format: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate streaming response with locking to prevent conflicts

        This method acquires a lock before streaming, ensuring only one
        stream is active at a time. This prevents interleaving when multiple
        coroutines attempt concurrent streaming.

        Args:
            messages: Conversation history
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (overrides default)
            response_format: Optional response format hint (e.g., "json")
            **kwargs: Additional provider-specific args

        Yields:
            Streaming chunks from LLM
        """
        async with self._lock:
            logger.debug("isolated_stream_acquired",
                        messages_count=len(messages))

            try:
                async for chunk in self.client.generate_stream(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature or self.temperature,
                    response_format=response_format
                ):
                    yield chunk

            finally:
                logger.debug("isolated_stream_released")

    def get_provider(self) -> str:
        """Get provider name"""
        return self.client.provider

    def get_model_name(self) -> str:
        """Get model name"""
        return self.client.model_name

    def get_base_url(self) -> str:
        """Get base URL"""
        return self.client.base_url
