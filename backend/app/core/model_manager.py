"""
Model Manager - Central management for model loading/unloading
"""

from typing import Optional
from dataclasses import dataclass
import asyncio
import structlog
from app.core.llm_client import LLMClient
from app.core.model_providers import get_provider

logger = structlog.get_logger()


@dataclass
class ModelConfig:
    """Model configuration"""
    provider: str
    model_name: str
    url: str
    context_window: int = 8192
    temperature: float = 0.7

    def __str__(self) -> str:
        return f"{self.provider}:{self.model_name}"

    def get_display_name(self) -> str:
        """Get human-readable display name"""
        return f"{self.provider.capitalize()} - {self.model_name}"


class ModelManager:
    """
    Manages model lifecycle with 16GB VRAM constraint

    Key responsibilities:
    - Load models on demand
    - Unload current model before loading new one
    - Track current model state
    - Prevent concurrent switches
    - Provider-specific unload strategies

    Implemented as singleton to ensure only one instance exists
    """

    _instance = None

    def __new__(cls):
        """
        Singleton pattern - ensure only one ModelManager instance exists

        This prevents multiple instances from managing models independently,
        which would break the single-model-in-VRAM constraint.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize model manager (only runs once due to singleton)"""
        # Prevent re-initialization if already initialized
        if hasattr(self, '_initialized'):
            return

        self.current_model: Optional[LLMClient] = None
        self.current_config: Optional[ModelConfig] = None
        self._switch_lock = asyncio.Lock()  # Prevent concurrent switches

        # Track in-flight requests to prevent mid-request unloading
        self._active_requests = 0
        self._request_lock = asyncio.Lock()

        self._initialized = True

        logger.info("model_manager_initialized")

    async def acquire_for_inference(self):
        """
        Acquire permission to make an inference request

        Should be called before each inference to prevent model unloading
        during active requests.
        """
        async with self._request_lock:
            self._active_requests += 1
            logger.debug("inference_acquired",
                        active_requests=self._active_requests)

    async def release_from_inference(self):
        """
        Release after inference completes

        Should be called after each inference (in finally block).
        """
        async with self._request_lock:
            self._active_requests -= 1
            logger.debug("inference_released",
                        active_requests=self._active_requests)

    async def _wait_for_requests_to_finish(self, timeout: float = 30.0):
        """
        Wait for all active requests to complete before unloading

        Args:
            timeout: Maximum seconds to wait

        Raises:
            TimeoutError: If requests don't finish within timeout
        """
        import time
        start_time = time.time()

        while self._active_requests > 0:
            if time.time() - start_time > timeout:
                raise TimeoutError(
                    f"Timed out waiting for {self._active_requests} requests to finish"
                )

            logger.info("waiting_for_requests",
                       active_requests=self._active_requests,
                       elapsed=time.time() - start_time)

            await asyncio.sleep(0.5)

        logger.info("all_requests_finished")

    async def switch_model(
        self,
        provider: str,
        model_name: str,
        url: str,
        context_window: int = 8192,
        temperature: float = 0.7
    ) -> LLMClient:
        """
        Switch to a different model (hot-swap)

        This is the main entry point for model switching.
        Handles the full workflow:
        1. Acquire lock
        2. Unload current model
        3. Wait for VRAM to free
        4. Load new model
        5. Update state
        6. Release lock

        Args:
            provider: Model provider ("ollama", "vllm", "llamacpp")
            model_name: Model identifier
            url: Provider base URL
            context_window: Context window size
            temperature: Sampling temperature

        Returns:
            New LLMClient instance

        Raises:
            RuntimeError: If switch fails
        """
        # Create config
        new_config = ModelConfig(
            provider=provider,
            model_name=model_name,
            url=url,
            context_window=context_window,
            temperature=temperature
        )

        # Check if already on this model
        if self._is_same_model(new_config):
            if self.current_config and (
                self.current_config.context_window != new_config.context_window
                or self.current_config.temperature != new_config.temperature
            ):
                self.current_config = new_config
                logger.info("model_config_updated",
                           model=str(new_config),
                           context_window=new_config.context_window,
                           temperature=new_config.temperature)
            else:
                logger.info("model_already_loaded",
                           model=str(new_config))
            return self.current_model

        # Acquire lock to prevent concurrent switches
        async with self._switch_lock:
            logger.info("model_switch_start",
                       old_model=str(self.current_config) if self.current_config else "none",
                       new_model=str(new_config))

            try:
                # Step 1: Unload current model
                if self.current_model:
                    await self._unload_current()

                # Step 2: Wait for VRAM to free
                await asyncio.sleep(2.0)  # Give VRAM time to clear

                # Step 3: Load new model
                new_model = await self._load_model(new_config)

                # Step 4: Update state
                self.current_model = new_model
                self.current_config = new_config

                logger.info("model_switch_complete",
                           model=str(new_config),
                           provider=provider)

                return new_model

            except Exception as e:
                logger.error("model_switch_failed",
                            old_model=str(self.current_config) if self.current_config else "none",
                            new_model=str(new_config),
                            error=str(e))

                # On failure, try to restore old model
                if self.current_config and not self.current_model:
                    logger.warning("attempting_rollback",
                                 model=str(self.current_config))
                    try:
                        self.current_model = await self._load_model(self.current_config)
                    except Exception as rollback_error:
                        logger.error("rollback_failed",
                                   error=str(rollback_error))

                raise RuntimeError(f"Model switch failed: {e}")

    async def _unload_current(self) -> None:
        """
        Unload currently loaded model

        Uses provider-specific strategy.
        Waits for in-flight requests to complete before unloading.
        """
        if not self.current_model or not self.current_config:
            logger.debug("no_model_to_unload")
            return

        # Wait for all active inference requests to complete
        await self._wait_for_requests_to_finish(timeout=30.0)

        logger.info("unloading_current_model",
                   model=str(self.current_config))

        # Get provider-specific strategy
        provider = get_provider(self.current_config.provider)

        if provider:
            try:
                success = await provider.unload_model(
                    model_name=self.current_config.model_name,
                    base_url=self.current_config.url
                )

                if not success:
                    logger.warning("provider_unload_failed",
                                 provider=self.current_config.provider,
                                 model=self.current_config.model_name)
            except NotImplementedError as e:
                # vLLM/llama.cpp don't support hot-swapping
                logger.warning("provider_unload_not_supported",
                             provider=self.current_config.provider,
                             error=str(e))
        else:
            logger.warning("unknown_provider_for_unload",
                         provider=self.current_config.provider)

        # Clear reference (Python GC will clean up)
        self.current_model = None

        logger.info("model_unloaded",
                   model=str(self.current_config))

    async def _load_model(self, config: ModelConfig) -> LLMClient:
        """
        Load a new model

        Args:
            config: Model configuration

        Returns:
            Initialized LLMClient

        Raises:
            RuntimeError: If load fails
        """
        logger.info("loading_model",
                   model=str(config))

        try:
            # Create LLMClient
            client = LLMClient(
                provider=config.provider,
                model_name=config.model_name,
                base_url=config.url
            )

            # Warmup inference to ensure model is loaded into VRAM
            # Without this, the model might not be in VRAM until first actual request,
            # causing OOM if another model is still loaded
            logger.info("warming_up_model",
                       model=str(config))

            warmup_messages = [{"role": "user", "content": "test"}]
            async for chunk in client.generate_stream(warmup_messages, max_tokens=1):
                break  # Just need one token to trigger VRAM load

            logger.info("model_warmed_up",
                       model=str(config))

            logger.info("model_loaded_successfully",
                       model=str(config))

            return client

        except Exception as e:
            logger.error("model_load_failed",
                        model=str(config),
                        error=str(e))
            raise RuntimeError(f"Failed to load model {config}: {e}")

    def _is_same_model(self, config: ModelConfig) -> bool:
        """
        Check if config matches current model

        Args:
            config: Model config to check

        Returns:
            True if same model
        """
        if not self.current_config:
            return False

        return (
            self.current_config.provider == config.provider and
            self.current_config.model_name == config.model_name and
            self.current_config.url == config.url
        )

    def get_current_model(self) -> Optional[LLMClient]:
        """
        Get currently loaded model

        Returns:
            Current LLMClient or None
        """
        return self.current_model

    def get_current_config(self) -> Optional[ModelConfig]:
        """
        Get current model configuration

        Returns:
            Current ModelConfig or None
        """
        return self.current_config

    def is_model_loaded(self) -> bool:
        """Check if a model is currently loaded"""
        return self.current_model is not None

    async def ensure_model_loaded(self, config: ModelConfig) -> LLMClient:
        """
        Ensure a model is loaded (load if not already)

        Args:
            config: Desired model config

        Returns:
            LLMClient instance
        """
        if self._is_same_model(config):
            if self.current_config and (
                self.current_config.context_window != config.context_window
                or self.current_config.temperature != config.temperature
            ):
                self.current_config = config
                logger.info("model_config_updated",
                           model=str(config),
                           context_window=config.context_window,
                           temperature=config.temperature)
            return self.current_model

        return await self.switch_model(
            provider=config.provider,
            model_name=config.model_name,
            url=config.url,
            context_window=config.context_window,
            temperature=config.temperature
        )

    async def shutdown(self) -> None:
        """
        Shutdown model manager

        Unloads current model gracefully.
        """
        logger.info("model_manager_shutting_down")

        async with self._switch_lock:
            if self.current_model:
                await self._unload_current()

        logger.info("model_manager_shutdown_complete")
