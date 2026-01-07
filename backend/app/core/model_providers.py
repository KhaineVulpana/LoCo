"""
Model Providers - Provider-specific strategies for model loading/unloading
"""

from abc import ABC, abstractmethod
from typing import Optional
import aiohttp
import asyncio
import structlog

logger = structlog.get_logger()


class ModelProvider(ABC):
    """Abstract base class for model providers"""

    @abstractmethod
    async def unload_model(self, model_name: str, base_url: str) -> bool:
        """
        Unload a model to free VRAM

        Args:
            model_name: Name of model to unload
            base_url: Provider base URL

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def verify_model_loaded(self, model_name: str, base_url: str) -> bool:
        """
        Verify if a model is currently loaded

        Args:
            model_name: Name of model
            base_url: Provider base URL

        Returns:
            True if loaded
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name"""
        pass


class OllamaProvider(ModelProvider):
    """Ollama-specific model management"""

    def get_provider_name(self) -> str:
        return "ollama"

    async def unload_model(self, model_name: str, base_url: str) -> bool:
        """
        Unload Ollama model

        IMPORTANT: We DO NOT use DELETE /api/delete because it's destructive
        - it removes the model files from disk, not just VRAM!

        Ollama auto-unloads models after 5-minute idle timeout.
        Trust the garbage collector - when we load a new model, Ollama
        will automatically unload the old one if VRAM is needed.
        """
        logger.info("ollama_model_unload_requested",
                   model_name=model_name,
                   base_url=base_url,
                   note="Trusting Ollama auto-unload (5min idle timeout)")

        # Just log and return success
        # Ollama will handle unloading automatically
        return True

    async def verify_model_loaded(self, model_name: str, base_url: str) -> bool:
        """
        Verify if Ollama model is loaded

        IMPORTANT: We cannot actually verify without triggering a load.
        Ollama doesn't have a "loaded models" endpoint, and sending a
        generate request would cause the model to load if it's not already.

        Since we have warmup inference in _load_model, we can trust that
        the model is loaded after that completes. Just return True.
        """
        logger.debug("ollama_verify_skipped",
                    model_name=model_name,
                    note="Trusting warmup inference from load")
        return True


class VLLMProvider(ModelProvider):
    """vLLM-specific model management"""

    def get_provider_name(self) -> str:
        return "vllm"

    async def unload_model(self, model_name: str, base_url: str) -> bool:
        """
        Unload vLLM model

        vLLM doesn't support hot-swapping models in the same server instance.
        To switch models, you need to:
        1. Stop the vLLM server
        2. Start a new vLLM server with the new model

        This is NOT supported in Sprint 4 (would require process management).
        """
        logger.error("vllm_unload_not_supported",
                    model_name=model_name,
                    message="vLLM requires server restart to change models")

        raise NotImplementedError(
            "vLLM does not support hot-swapping. "
            "To change models, restart the vLLM server with the new model."
        )

    async def verify_model_loaded(self, model_name: str, base_url: str) -> bool:
        """
        Verify if vLLM model is loaded

        vLLM has a /v1/models endpoint that lists available models.
        """
        try:
            models_url = f"{base_url}/v1/models"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    models_url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("data", [])
                        return any(m.get("id") == model_name for m in models)
                    return False

        except Exception as e:
            logger.debug("vllm_verify_failed",
                        model_name=model_name,
                        error=str(e))
            return False


class LlamaCppProvider(ModelProvider):
    """llama.cpp-specific model management"""

    def get_provider_name(self) -> str:
        return "llamacpp"

    async def unload_model(self, model_name: str, base_url: str) -> bool:
        """
        Unload llama.cpp model

        llama.cpp server loads ONE model at startup and doesn't support
        hot-swapping. To change models, you must restart the server.

        Not supported in Sprint 4.
        """
        logger.error("llamacpp_unload_not_supported",
                    model_name=model_name,
                    message="llama.cpp requires server restart to change models")

        raise NotImplementedError(
            "llama.cpp does not support hot-swapping. "
            "To change models, restart the llama.cpp server with the new model."
        )

    async def verify_model_loaded(self, model_name: str, base_url: str) -> bool:
        """
        Verify if llama.cpp model is loaded

        llama.cpp has a /health endpoint we can check.
        """
        try:
            health_url = f"{base_url}/health"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    health_url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200

        except Exception as e:
            logger.debug("llamacpp_verify_failed",
                        model_name=model_name,
                        error=str(e))
            return False


# Provider registry
PROVIDERS = {
    "ollama": OllamaProvider(),
    "vllm": VLLMProvider(),
    "llamacpp": LlamaCppProvider(),
}


def get_provider(provider_name: str) -> Optional[ModelProvider]:
    """
    Get provider instance by name

    Args:
        provider_name: Provider identifier (e.g., "ollama")

    Returns:
        ModelProvider instance or None
    """
    provider = PROVIDERS.get(provider_name.lower())

    if provider is None:
        logger.warning("unknown_provider",
                      provider_name=provider_name,
                      available=list(PROVIDERS.keys()))

    return provider
