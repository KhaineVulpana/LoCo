"""
Runtime singletons and dependency helpers.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from app.core.embedding_manager import EmbeddingManager
from app.core.model_manager import ModelManager
from app.core.vector_store import VectorStore


embedding_manager: Optional[EmbeddingManager] = None
vector_store: Optional[VectorStore] = None
model_manager: Optional[ModelManager] = None


def get_embedding_manager() -> EmbeddingManager:
    """Get the global embedding manager instance."""
    if embedding_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Embedding manager not initialized. Qdrant may not be available."
        )
    return embedding_manager


def get_vector_store() -> VectorStore:
    """Get the global vector store instance."""
    if vector_store is None:
        raise HTTPException(
            status_code=503,
            detail="Vector store not initialized. Qdrant may not be available."
        )
    return vector_store


def get_model_manager() -> ModelManager:
    """Get the global model manager instance."""
    if model_manager is None:
        raise HTTPException(status_code=500, detail="Model manager not initialized")
    return model_manager
