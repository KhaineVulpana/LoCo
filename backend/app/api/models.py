"""
Model API - Endpoints for model switching and management
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

router = APIRouter()


# Request/Response models
class ModelSwitchRequest(BaseModel):
    """Request to switch model"""
    provider: str  # "ollama", "vllm", "llamacpp"
    model_name: str
    url: str
    context_window: int = 8192
    temperature: float = 0.7


class ModelSwitchResponse(BaseModel):
    """Response after model switch"""
    success: bool
    old_model: Optional[str]
    new_model: str
    message: str


class CurrentModelResponse(BaseModel):
    """Current model information"""
    provider: str
    model_name: str
    url: str
    context_window: int
    temperature: float
    display_name: str


class ModelStatusResponse(BaseModel):
    """Model manager status"""
    is_loaded: bool
    current_model: Optional[CurrentModelResponse]


# Dependency to get model manager
def get_model_manager():
    """Get model manager from app state"""
    from app.main import model_manager
    if model_manager is None:
        raise HTTPException(status_code=500, detail="Model manager not initialized")
    return model_manager


@router.get("/status", response_model=ModelStatusResponse)
async def get_model_status(
    model_manager = Depends(get_model_manager)
):
    """
    Get current model status

    Returns:
        Model status and current model info
    """
    is_loaded = model_manager.is_model_loaded()

    current_model = None
    if is_loaded:
        config = model_manager.get_current_config()
        current_model = CurrentModelResponse(
            provider=config.provider,
            model_name=config.model_name,
            url=config.url,
            context_window=config.context_window,
            temperature=config.temperature,
            display_name=config.get_display_name()
        )

    logger.info("model_status_retrieved",
               is_loaded=is_loaded,
               model=str(config) if is_loaded else "none")

    return ModelStatusResponse(
        is_loaded=is_loaded,
        current_model=current_model
    )


@router.post("/switch", response_model=ModelSwitchResponse)
async def switch_model(
    request: ModelSwitchRequest,
    model_manager = Depends(get_model_manager)
):
    """
    Switch to a different model

    This triggers model hot-swapping:
    1. Unload current model
    2. Wait for VRAM to free
    3. Load new model

    Typically takes 10-30 seconds.

    Args:
        request: Model switch request

    Returns:
        Switch confirmation
    """
    # Get old model
    old_config = model_manager.get_current_config()
    old_model_str = str(old_config) if old_config else "none"

    logger.info("model_switch_requested",
               old_model=old_model_str,
               new_model=f"{request.provider}:{request.model_name}")

    try:
        # Perform switch
        new_client = await model_manager.switch_model(
            provider=request.provider,
            model_name=request.model_name,
            url=request.url,
            context_window=request.context_window,
            temperature=request.temperature
        )

        new_model_str = f"{request.provider}:{request.model_name}"

        logger.info("model_switched_via_api",
                   old_model=old_model_str,
                   new_model=new_model_str)

        return ModelSwitchResponse(
            success=True,
            old_model=old_model_str if old_config else None,
            new_model=new_model_str,
            message=f"Switched from '{old_model_str}' to '{new_model_str}'"
        )

    except Exception as e:
        logger.error("model_switch_api_failed",
                    old_model=old_model_str,
                    new_model=f"{request.provider}:{request.model_name}",
                    error=str(e))

        raise HTTPException(
            status_code=500,
            detail=f"Model switch failed: {str(e)}"
        )


@router.get("/current", response_model=CurrentModelResponse)
async def get_current_model(
    model_manager = Depends(get_model_manager)
):
    """
    Get currently loaded model

    Returns:
        Current model configuration

    Raises:
        404: If no model is loaded
    """
    if not model_manager.is_model_loaded():
        raise HTTPException(
            status_code=404,
            detail="No model currently loaded"
        )

    config = model_manager.get_current_config()

    logger.info("current_model_retrieved",
               model=str(config))

    return CurrentModelResponse(
        provider=config.provider,
        model_name=config.model_name,
        url=config.url,
        context_window=config.context_window,
        temperature=config.temperature,
        display_name=config.get_display_name()
    )


@router.post("/unload")
async def unload_current_model(
    model_manager = Depends(get_model_manager)
):
    """
    Unload current model to free VRAM

    Returns:
        Unload confirmation
    """
    if not model_manager.is_model_loaded():
        raise HTTPException(
            status_code=400,
            detail="No model currently loaded"
        )

    old_model = str(model_manager.get_current_config())

    logger.info("model_unload_requested",
               model=old_model)

    try:
        await model_manager._unload_current()

        logger.info("model_unloaded_via_api",
                   model=old_model)

        return {
            "success": True,
            "message": f"Unloaded model '{old_model}'",
            "model": old_model
        }

    except Exception as e:
        logger.error("model_unload_api_failed",
                    model=old_model,
                    error=str(e))

        raise HTTPException(
            status_code=500,
            detail=f"Model unload failed: {str(e)}"
        )
