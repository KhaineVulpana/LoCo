"""
3D-gen training data loader for RAG indexing
"""

from pathlib import Path
from typing import Any, Dict, Optional
import structlog

from app.indexing.domain_indexer import KnowledgeIndexer

logger = structlog.get_logger()

DEFAULT_TRAINING_PATH = Path("backend") / "data" / "3d-gen" / "training_data_complete_1194.jsonl"


def resolve_training_path(path_override: Optional[str] = None) -> Path:
    """Resolve training data path relative to repo root when needed."""
    if path_override:
        path = Path(path_override)
    else:
        path = DEFAULT_TRAINING_PATH

    if path.is_absolute():
        return path

    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / path


async def ensure_3d_gen_training_data(
    embedding_manager,
    vector_store,
    path_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ensure 3D-gen training data is indexed into loco_rag_3d-gen.
    """
    frontend_id = "3d-gen"
    collection_name = f"loco_rag_{frontend_id}"
    training_path = resolve_training_path(path_override)

    vector_store.create_collection(
        collection_name=collection_name,
        vector_size=embedding_manager.get_dimensions()
    )

    try:
        info = vector_store.get_collection_info(collection_name)
        points_count = info.get("points_count", 0)
    except Exception:
        points_count = 0

    if points_count > 0:
        logger.info("training_data_already_indexed",
                   frontend_id=frontend_id,
                   points=points_count)
        return {
            "status": "already_indexed",
            "points": points_count,
            "path": str(training_path)
        }

    if not training_path.exists():
        logger.error("training_data_missing",
                    frontend_id=frontend_id,
                    path=str(training_path))
        return {
            "status": "missing",
            "path": str(training_path)
        }

    indexer = KnowledgeIndexer(
        frontend_id=frontend_id,
        embedding_manager=embedding_manager,
        vector_store=vector_store
    )

    stats = await indexer.index_training_data(str(training_path))
    return {
        "status": "indexed",
        "stats": stats,
        "path": str(training_path)
    }
