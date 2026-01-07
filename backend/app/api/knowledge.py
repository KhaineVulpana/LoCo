"""
Knowledge Management API - Index and retrieve operational knowledge
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import structlog

from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore
from app.indexing.domain_indexer import KnowledgeIndexer
from app.retrieval.retriever import Retriever
from app.main import get_embedding_manager, get_vector_store

logger = structlog.get_logger()

router = APIRouter()


class IndexDocsRequest(BaseModel):
    docs_path: str


class IndexTrainingRequest(BaseModel):
    jsonl_path: str


class RetrieveRequest(BaseModel):
    query: str
    limit: int = 10
    score_threshold: float = 0.5


@router.post("/{frontend_id}/index-docs")
async def index_documentation(
    frontend_id: str,
    request: IndexDocsRequest,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    Index documentation files for a frontend

    Args:
        frontend_id: Frontend identifier (vscode, android, 3d-gen)
        request: Contains docs_path
    """
    logger.info("index_docs_request", frontend_id=frontend_id, path=request.docs_path)

    try:
        indexer = KnowledgeIndexer(
            frontend_id=frontend_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store
        )

        stats = await indexer.index_documentation(request.docs_path)

        return {
            "success": True,
            "frontend_id": frontend_id,
            "stats": stats
        }

    except Exception as e:
        logger.error("index_docs_failed", frontend_id=frontend_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{frontend_id}/index-training")
async def index_training_data(
    frontend_id: str,
    request: IndexTrainingRequest,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    Index training data (JSONL) for a frontend

    Args:
        frontend_id: Frontend identifier (vscode, android, 3d-gen)
        request: Contains jsonl_path
    """
    logger.info("index_training_request", frontend_id=frontend_id, path=request.jsonl_path)

    try:
        indexer = KnowledgeIndexer(
            frontend_id=frontend_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store
        )

        stats = await indexer.index_training_data(request.jsonl_path)

        return {
            "success": True,
            "frontend_id": frontend_id,
            "stats": stats
        }

    except Exception as e:
        logger.error("index_training_failed", frontend_id=frontend_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{frontend_id}/stats")
async def get_knowledge_stats(
    frontend_id: str,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    Get statistics about indexed knowledge for a frontend

    Args:
        frontend_id: Frontend identifier (vscode, android, 3d-gen)
    """
    try:
        retriever = Retriever(
            frontend_id=frontend_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store
        )

        stats = retriever.get_collection_stats()

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        logger.error("get_stats_failed", frontend_id=frontend_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{frontend_id}/retrieve")
async def retrieve_knowledge(
    frontend_id: str,
    request: RetrieveRequest,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    Retrieve relevant knowledge for a query (for testing/debugging)

    Args:
        frontend_id: Frontend identifier (vscode, android, 3d-gen)
        request: Contains query and retrieval params
    """
    try:
        retriever = Retriever(
            frontend_id=frontend_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store
        )

        results = await retriever.retrieve(
            query=request.query,
            limit=request.limit,
            score_threshold=request.score_threshold
        )

        return {
            "success": True,
            "results": [
                {
                    "score": result.score,
                    "source": result.source,
                    "content": result.content,
                    "metadata": result.metadata
                }
                for result in results
            ]
        }

    except Exception as e:
        logger.error("retrieve_failed", frontend_id=frontend_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{frontend_id}")
async def clear_knowledge(
    frontend_id: str,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    Clear all knowledge for a frontend

    Args:
        frontend_id: Frontend identifier (vscode, android, 3d-gen)
    """
    logger.info("clear_knowledge_request", frontend_id=frontend_id)

    try:
        indexer = KnowledgeIndexer(
            frontend_id=frontend_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store
        )

        await indexer.clear_knowledge()

        return {
            "success": True,
            "frontend_id": frontend_id,
            "message": "Knowledge cleared successfully"
        }

    except Exception as e:
        logger.error("clear_knowledge_failed", frontend_id=frontend_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
