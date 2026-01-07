"""
ACE Management API - Manage ACE playbook bullets in vector storage
"""

from typing import Any, Dict, List, Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.ace.playbook import Playbook
from app.core.embedding_manager import EmbeddingManager
from app.core.vector_store import VectorStore
from app.main import get_embedding_manager, get_vector_store

logger = structlog.get_logger()

router = APIRouter()


class AceBulletCreate(BaseModel):
    section: str
    content: str
    bullet_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    helpful_count: int = 0
    harmful_count: int = 0


class AceBulletUpdate(BaseModel):
    section: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    helpful_count: Optional[int] = None
    harmful_count: Optional[int] = None


class AceRetrieveRequest(BaseModel):
    query: str
    limit: int = 5
    score_threshold: float = 0.5


class AceFeedbackItem(BaseModel):
    bullet_id: str
    tag: str


class AceFeedbackRequest(BaseModel):
    feedback: List[AceFeedbackItem]


@router.get("/{frontend_id}/bullets")
def list_bullets(
    frontend_id: str,
    limit: int = 1000,
    vector_store: VectorStore = Depends(get_vector_store)
):
    """List ACE bullets for a frontend"""
    collection_name = f"loco_ace_{frontend_id}"

    try:
        playbook = Playbook.load_from_vector_db(
            vector_store=vector_store,
            collection_name=collection_name,
            max_bullets=limit
        )
    except Exception as e:
        logger.error("ace_list_bullets_failed",
                    frontend_id=frontend_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "success": True,
        "frontend_id": frontend_id,
        "bullets": [b.to_dict() for b in playbook.get_all_bullets()]
    }


@router.post("/{frontend_id}/bullets")
def create_bullet(
    frontend_id: str,
    request: AceBulletCreate,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Create a new ACE bullet"""
    collection_name = f"loco_ace_{frontend_id}"

    try:
        vector_store.create_collection(
            collection_name=collection_name,
            vector_size=embedding_manager.get_dimensions()
        )

        playbook = Playbook()
        bullet_id = playbook.add_bullet(
            section=request.section,
            content=request.content,
            bullet_id=request.bullet_id
        )
        playbook.update_bullet(
            bullet_id,
            metadata=request.metadata,
            helpful_count=request.helpful_count,
            harmful_count=request.harmful_count
        )

        success = playbook.save_bullet_to_vector_db(
            bullet_id=bullet_id,
            vector_store=vector_store,
            embedding_manager=embedding_manager,
            collection_name=collection_name
        )
        if not success:
            raise RuntimeError("Failed to save bullet to vector DB")

        bullet = playbook.get_bullet_by_id(bullet_id)
        return {
            "success": True,
            "frontend_id": frontend_id,
            "bullet": bullet.to_dict() if bullet else None
        }
    except Exception as e:
        logger.error("ace_create_bullet_failed",
                    frontend_id=frontend_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{frontend_id}/bullets/{bullet_id}")
def update_bullet(
    frontend_id: str,
    bullet_id: str,
    request: AceBulletUpdate,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Update an existing ACE bullet"""
    collection_name = f"loco_ace_{frontend_id}"

    try:
        playbook = Playbook.load_from_vector_db(
            vector_store=vector_store,
            collection_name=collection_name
        )
        bullet = playbook.get_bullet_by_id(bullet_id)
        if not bullet:
            raise HTTPException(status_code=404, detail="Bullet not found")

        updates = {}
        if request.section is not None:
            updates["section"] = request.section
        if request.content is not None:
            updates["content"] = request.content
        if request.metadata is not None:
            updates["metadata"] = request.metadata
        if request.helpful_count is not None:
            updates["helpful_count"] = request.helpful_count
        if request.harmful_count is not None:
            updates["harmful_count"] = request.harmful_count

        if updates:
            playbook.update_bullet(bullet_id, **updates)

        success = playbook.save_bullet_to_vector_db(
            bullet_id=bullet_id,
            vector_store=vector_store,
            embedding_manager=embedding_manager,
            collection_name=collection_name
        )
        if not success:
            raise RuntimeError("Failed to update bullet in vector DB")

        updated = playbook.get_bullet_by_id(bullet_id)
        return {
            "success": True,
            "frontend_id": frontend_id,
            "bullet": updated.to_dict() if updated else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("ace_update_bullet_failed",
                    frontend_id=frontend_id,
                    bullet_id=bullet_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{frontend_id}/bullets/{bullet_id}")
def delete_bullet(
    frontend_id: str,
    bullet_id: str,
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Delete an ACE bullet"""
    collection_name = f"loco_ace_{frontend_id}"

    playbook = Playbook()
    success = playbook.delete_bullet_from_vector_db(
        bullet_id=bullet_id,
        vector_store=vector_store,
        collection_name=collection_name
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete bullet")

    return {
        "success": True,
        "frontend_id": frontend_id,
        "bullet_id": bullet_id
    }


@router.post("/{frontend_id}/retrieve")
def retrieve_bullets(
    frontend_id: str,
    request: AceRetrieveRequest,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Retrieve relevant ACE bullets for a query"""
    collection_name = f"loco_ace_{frontend_id}"
    playbook = Playbook()

    results = playbook.retrieve_relevant_bullets(
        query=request.query,
        embedding_manager=embedding_manager,
        vector_store=vector_store,
        collection_name=collection_name,
        limit=request.limit,
        score_threshold=request.score_threshold
    )

    return {
        "success": True,
        "frontend_id": frontend_id,
        "results": [
            {
                "score": score,
                "bullet": bullet.to_dict()
            }
            for bullet, score in results
        ]
    }


@router.post("/{frontend_id}/feedback")
def apply_feedback(
    frontend_id: str,
    request: AceFeedbackRequest,
    embedding_manager: EmbeddingManager = Depends(get_embedding_manager),
    vector_store: VectorStore = Depends(get_vector_store)
):
    """Apply helpful/harmful feedback to bullets"""
    collection_name = f"loco_ace_{frontend_id}"

    try:
        playbook = Playbook.load_from_vector_db(
            vector_store=vector_store,
            collection_name=collection_name
        )

        feedback_payload = [
            {"bullet_id": item.bullet_id, "tag": item.tag}
            for item in request.feedback
        ]
        playbook.apply_bullet_feedback(feedback_payload)

        for item in request.feedback:
            playbook.save_bullet_to_vector_db(
                bullet_id=item.bullet_id,
                vector_store=vector_store,
                embedding_manager=embedding_manager,
                collection_name=collection_name
            )

        return {
            "success": True,
            "frontend_id": frontend_id,
            "updated": len(request.feedback)
        }
    except Exception as e:
        logger.error("ace_feedback_failed",
                    frontend_id=frontend_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
