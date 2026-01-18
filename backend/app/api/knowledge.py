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
from app.core.runtime import get_embedding_manager, get_vector_store

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


@router.post("/{module_id}/index-docs")
async def index_documentation(
    module_id: str,
    request: IndexDocsRequest,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    Index documentation files for a module

    Args:
        module_id: Module identifier (vscode, android, 3d-gen)
        request: Contains docs_path
    """
    logger.info("index_docs_request", module_id=module_id, path=request.docs_path)

    try:
        indexer = KnowledgeIndexer(
            module_id=module_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store
        )

        stats = await indexer.index_documentation(request.docs_path)

        return {
            "success": True,
            "module_id": module_id,
            "stats": stats
        }

    except Exception as e:
        logger.error("index_docs_failed", module_id=module_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{module_id}/index-training")
async def index_training_data(
    module_id: str,
    request: IndexTrainingRequest,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    Index training data (JSONL) for a module

    Args:
        module_id: Module identifier (vscode, android, 3d-gen)
        request: Contains jsonl_path
    """
    logger.info("index_training_request", module_id=module_id, path=request.jsonl_path)

    try:
        indexer = KnowledgeIndexer(
            module_id=module_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store
        )

        stats = await indexer.index_training_data(request.jsonl_path)

        return {
            "success": True,
            "module_id": module_id,
            "stats": stats
        }

    except Exception as e:
        logger.error("index_training_failed", module_id=module_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{module_id}/stats")
async def get_knowledge_stats(
    module_id: str,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    Get statistics about indexed knowledge for a module

    Args:
        module_id: Module identifier (vscode, android, 3d-gen)
    """
    try:
        retriever = Retriever(
            module_id=module_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store
        )

        stats = retriever.get_collection_stats()

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        logger.error("get_stats_failed", module_id=module_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{module_id}/items")
async def list_knowledge_items(
    module_id: str,
    limit: int = 200,
    offset: Optional[str] = None,
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    List indexed knowledge chunks for a module.

    Returns payload metadata and content for inspection.
    """
    collection_name = f"loco_rag_{module_id}"
    try:
        page = vector_store.scroll(
            collection_name=collection_name,
            limit=limit,
            offset=offset
        )
        items = []
        for point in page.get("points", []):
            payload = point.get("payload") or {}
            items.append({
                "id": point.get("id"),
                "payload": payload
            })

        return {
            "success": True,
            "module_id": module_id,
            "collection": collection_name,
            "items": items,
            "next_offset": page.get("next_offset")
        }
    except Exception as e:
        logger.error("list_knowledge_items_failed", module_id=module_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{module_id}/retrieve")
async def retrieve_knowledge(
    module_id: str,
    request: RetrieveRequest,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    Retrieve relevant knowledge for a query (for testing/debugging)

    Args:
        module_id: Module identifier (vscode, android, 3d-gen)
        request: Contains query and retrieval params
    """
    try:
        retriever = Retriever(
            module_id=module_id,
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
        logger.error("retrieve_failed", module_id=module_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{module_id}")
async def clear_knowledge(
    module_id: str,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """
    Clear all knowledge for a module

    Args:
        module_id: Module identifier (vscode, android, 3d-gen)
    """
    logger.info("clear_knowledge_request", module_id=module_id)

    try:
        indexer = KnowledgeIndexer(
            module_id=module_id,
            embedding_manager=embedding_manager,
            vector_store=vector_store
        )

        await indexer.clear_knowledge()

        return {
            "success": True,
            "module_id": module_id,
            "message": "Knowledge cleared successfully"
        }

    except Exception as e:
        logger.error("clear_knowledge_failed", module_id=module_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
