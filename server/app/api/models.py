"""
Model API endpoints
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

from app.core.config import settings

router = APIRouter()


class ModelInfo(BaseModel):
    provider: str
    model_name: str
    context_window: int
    capabilities: List[str]


class ModelConfig(BaseModel):
    provider: str
    model_name: str
    url: str


@router.get("/current", response_model=ModelInfo)
async def get_current_model():
    """Get current model configuration"""
    return ModelInfo(
        provider=settings.MODEL_PROVIDER,
        model_name=settings.MODEL_NAME,
        context_window=settings.MAX_CONTEXT_TOKENS,
        capabilities=["chat", "code_completion", "refactor"]
    )


@router.get("", response_model=List[ModelInfo])
async def list_available_models():
    """List available models (placeholder)"""
    # In production, this would query Ollama/vLLM/llama.cpp for available models
    return [
        ModelInfo(
            provider="ollama",
            model_name="codellama:13b",
            context_window=16384,
            capabilities=["chat", "code_completion", "refactor"]
        ),
        ModelInfo(
            provider="ollama",
            model_name="codellama:7b",
            context_window=8192,
            capabilities=["chat", "code_completion"]
        )
    ]
